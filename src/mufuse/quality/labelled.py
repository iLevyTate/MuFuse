"""The guided labelled session and its scorer (contracts/labelled-session.md).

The cue is the label. One cue list drives the screen, the markers written into the recording, the
scripted wearer of the rehearsal, and the scorer. A green rehearsal proves the pipeline, not the
physiology; the gate is scored on a session recorded with the headband.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, cast, get_args

from mufuse.acquisition.simulated import Wearer
from mufuse.guide import Cue, Guide, action
from mufuse.quality.answer import FOREHEAD, QualityAnswer, SessionQuality, Span
from mufuse.quality.rules import RULES_VERSION
from mufuse.recording.format import Marker

CueKind = Literal["blink", "clench", "turn", "lift", "down", "quiet_open", "quiet_closed", "end"]
PREFIX = "q:"
ALLOWED_S = 2.0  # a mark counts from its cue to this long after it
QUIET_S = 60.0  # each quiet block
QUIET_FROM_S, QUIET_UNTIL_S = 3.0, 1.0  # quiet is judged from cue + 3 s to block end - 1 s
LEFT_OUT_MAX = 0.10  # more of the quiet stretches unjudged than this: quiet is not scored
END_S = 565.0
RUN_S = 567.0  # the recording runs past `q:end` so that the marker is written
REACT_S = 0.4  # the rehearsal's wearer follows a cue this late
PASS_SHARE = 0.9  # 18 of 20, 9 of 10
QUIET_LIMITS = (0.05, 0.05, 2.0)  # tension share, movement share, blinks per minute eyes closed

BLINKS = [150.0 + 4 * k for k in range(20)]
CLENCHES = [240.0 + 5 * k for k in range(20)]
TURNS = [350.0 + 5 * k for k in range(20)]
LIFTS = [(460.0 + 10 * k, FOREHEAD[k % 2]) for k in range(10)]
LIFT_S = 5.0


@dataclass(frozen=True)
class LabelCue:
    """One cue: seconds (after streaming starts in the schedule, on the sample clock in a
    recording), its kind, and the sensor of a lift."""

    t: float
    kind: CueKind
    sensor: str | None = None

    @property
    def label(self) -> str:
        return f"{PREFIX}{self.kind}" + (f":{self.sensor}" if self.sensor else "")

    @classmethod
    def parse(cls, t: float, label: str) -> LabelCue | None:
        if not label.startswith(PREFIX):
            return None
        kind, _, sensor = label.removeprefix(PREFIX).partition(":")
        if kind not in get_args(CueKind):
            return None
        needs_sensor = kind in ("lift", "down")
        if needs_sensor != bool(sensor) or (sensor and sensor not in FOREHEAD):
            return None
        return cls(t, cast(CueKind, kind), sensor or None)


def schedule() -> tuple[LabelCue, ...]:
    """Every cue of the session, in time order."""
    cues = [LabelCue(20.0, "quiet_open"), LabelCue(80.0, "quiet_closed")]
    cues += [LabelCue(t, "blink") for t in BLINKS]
    cues += [LabelCue(t, "clench") for t in CLENCHES]
    cues += [LabelCue(t, "turn") for t in TURNS]
    for t, sensor in LIFTS:
        cues += [LabelCue(t, "lift", sensor), LabelCue(t + LIFT_S, "down", sensor)]
    cues.append(LabelCue(END_S, "end"))
    return tuple(cues)


_SIDE = {"AF7": "left", "AF8": "right"}


def labelled_guide() -> Guide:
    """The screen of the session: one instruction at a time, counted within each block."""
    by_time = {(c.t, c.kind): c for c in schedule()}

    def marker(t: float, kind: CueKind) -> str:
        return by_time[(t, kind)].label

    cues = [Cue(0.0, "Settle: sit still and check that the sensor panel is good")]
    cues += action(20.0, "Sit still, eyes open, look at one spot", marker(20.0, "quiet_open"))
    cues += action(80.0, "Sit still, eyes closed until the bell", marker(80.0, "quiet_closed"))
    cues.append(Cue(140.0, "Open your eyes. Next: blinks", bell=True))
    cues.append(Cue(147.0, "Get ready: blink once at each cue"))
    for k, t in enumerate(BLINKS, 1):
        cues.append(Cue(t, f"Blink once now (Blink {k} of 20)", marker(t, "blink")))
    cues.append(Cue(230.0, "Next: jaw clenches, about 1 s each"))
    cues.append(Cue(237.0, "Get ready: clench your jaw for about 1 s at each cue"))
    for k, t in enumerate(CLENCHES, 1):
        cues.append(Cue(t, f"Clench your jaw now (Clench {k} of 20)", marker(t, "clench")))
        cues.append(Cue(t + 1.5, f"Let go (Clench {k} of 20)"))
    cues.append(Cue(340.0, "Next: head turns, to one side and back"))
    cues.append(Cue(347.0, "Get ready: turn your head to one side and back at each cue"))
    for k, t in enumerate(TURNS, 1):
        cues.append(
            Cue(t, f"Turn your head to one side and back (Turn {k} of 20)", marker(t, "turn"))
        )
        cues.append(Cue(t + 2.5, f"Hold still (Turn {k} of 20)"))
    cues.append(Cue(450.0, "Next: lift a forehead sensor off the skin for 5 s"))
    cues.append(Cue(457.0, "Get ready: lift the sensor named on screen with one finger"))
    for k, (t, sensor) in enumerate(LIFTS, 1):
        side = _SIDE[sensor]
        lift, down = marker(t, "lift"), marker(t + LIFT_S, "down")
        cues.append(Cue(t, f"Lift {sensor} ({side} forehead) off the skin ({k} of 10)", lift))
        cues.append(Cue(t + LIFT_S, f"Put {sensor} back on the skin ({k} of 10)", down))
    cues.append(Cue(END_S, "Done. Saving and scoring", marker(END_S, "end")))
    return Guide(cues=tuple(cues), duration=RUN_S, title="Labelled session · signal quality (002)")


def cues_from_markers(markers: Sequence[Marker]) -> tuple[LabelCue, ...]:
    """The cues of a recording: its system markers whose label starts with `q:`."""
    found = (LabelCue.parse(m.t, m.label) for m in markers if m.kind == "system")
    return tuple(sorted((c for c in found if c is not None), key=lambda c: c.t))


def rehearsal_wearer(react_s: float = REACT_S) -> Wearer:
    """A simulated wearer who follows every cue `react_s` late (research R14)."""
    return Wearer(
        blinks=tuple((t + react_s, t + react_s + 0.5) for t in BLINKS),  # one blink each
        clench=tuple((t + react_s, t + react_s + 1.0) for t in CLENCHES),
        turns=tuple((t + react_s, t + react_s + 2.0) for t in TURNS),
        lifted=tuple((t + react_s, t + LIFT_S + react_s, s) for t, s in LIFTS),
    )


# Scoring -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class KindScore:
    found: int
    total: int
    passed: bool | None  # None: not scored (no cues)


@dataclass(frozen=True)
class QuietScore:
    tension_share: float | None
    movement_share: float | None
    blinks_per_min_closed: float | None
    false_marks: int
    passed: bool | None  # None: not scored
    not_scored: str = ""  # why, when it is not


@dataclass(frozen=True)
class ScoreReport:
    """Numbers only: no signal, no device name, no path (data-model.md, ScoreReport)."""

    rules: str
    allowed_s: float
    blinks: KindScore
    clenches: KindScore
    turns: KindScore
    quiet: QuietScore
    lifts: KindScore
    replay_identical: bool | None = None  # None: not checked

    @property
    def passed(self) -> bool:
        parts = (self.blinks, self.clenches, self.turns, self.quiet, self.lifts)
        return all(p.passed is True for p in parts) and self.replay_identical is not False


def kind_score(found: int, total: int) -> KindScore:
    if total == 0:
        return KindScore(0, 0, None)
    return KindScore(found, total, found >= math.ceil(PASS_SHARE * total - 1e-9))


def _judged(quality: SessionQuality) -> list[QualityAnswer]:
    return [a for a in quality.answers if not a.no_data]


def _stretch_start(answers: Sequence[QualityAnswer], t: float) -> float:
    """The start of the stretch that contains `t` (`t` itself when it lies in no stretch)."""
    for a in answers:
        if a.start <= t < a.end:
            return a.start
    return t


def span_found(answers: Sequence[QualityAnswer], spans: Sequence[Span], cue: float) -> bool:
    first = _stretch_start(answers, cue)
    return any(first - 1e-9 <= s.start <= cue + ALLOWED_S + 1e-9 for s in spans)


def blinks_found(quality: SessionQuality, cues: Sequence[float]) -> int:
    used: set[int] = set()
    found = 0
    for cue in cues:
        for i, blink in enumerate(quality.blinks):
            if i not in used and cue <= blink.t <= cue + ALLOWED_S:
                used.add(i)
                found += 1
                break
    return found


def _quiet(quality: SessionQuality, cues: Sequence[LabelCue]) -> QuietScore:
    answers = _judged(quality)
    blocks = [(c, c.t + QUIET_FROM_S, c.t + QUIET_S - QUIET_UNTIL_S) for c in cues]
    blocks = [(c, a, b) for c, a, b in blocks if c.kind in ("quiet_open", "quiet_closed")]
    if not blocks:
        return QuietScore(None, None, None, 0, None, "no quiet cues")
    quiet = [(c, s) for c, a, b in blocks for s in answers if s.start >= a and s.end <= b]
    closed = [s for c, s in quiet if c.kind == "quiet_closed"]
    stretches = [s for _, s in quiet]
    if not stretches:
        return QuietScore(None, None, None, 0, None, "no quiet stretch was judged")

    def share(marked: list[bool]) -> float | None:
        return sum(marked) / len(marked) if marked else None

    tension = [s.tension == "yes" for s in stretches if s.tension != "unavailable"]
    movement = [s.movement == "moving" for s in stretches if s.movement != "unknown"]
    seen_closed = [s for s in closed if s.eye != "unavailable"]
    in_closed = [b for b in quality.blinks if any(s.start <= b.t < s.end for s in closed)]
    rate = len(in_closed) / (len(seen_closed) / 60.0) if seen_closed else None
    starts_in_quiet = [
        span
        for span in (*quality.tension_spans, *quality.movement_spans)
        if any(s.start <= span.start < s.end for s in stretches)
    ]
    false_marks = len(starts_in_quiet) + len(in_closed)
    left_out = [
        len(stretches) - len(tension),
        len(stretches) - len(movement),
        len(closed) - len(seen_closed),
    ]
    if max(left_out) > LEFT_OUT_MAX * len(stretches) or (closed and rate is None):
        reason = "more than 10% of the quiet stretches could not be judged"
        return QuietScore(share(tension), share(movement), rate, false_marks, None, reason)
    values = (share(tension), share(movement), rate)
    passed = all(v is None or v <= limit for v, limit in zip(values, QUIET_LIMITS, strict=True))
    return QuietScore(*values, false_marks, passed)


def _lift_passes(answers: Sequence[QualityAnswer], lift: LabelCue, down: float) -> bool:
    sensor = lift.sensor or ""
    after = [a for a in answers if a.start >= lift.t - 1e-9]
    first = next((a for a in after if a.state(sensor).state != "good"), None)
    if first is None or first.start > lift.t + 4.0 + 1e-9:
        return False
    t = first.start
    lost = any(
        a.state(sensor).state == "none" and a.end <= t + ALLOWED_S + 1e-9
        for a in after
        if a.start >= t
    )
    run = longest = 0
    for a in after:
        if a.start >= down:
            break
        run = run + 1 if a.state(sensor).state == "noisy" else 0
        longest = max(longest, run)
    return lost and longest <= 2


def score(
    quality: SessionQuality, cues: Sequence[LabelCue], *, replay: bool | None = None
) -> ScoreReport:
    """The score of a labelled session; `replay` is whether live equalled `judge()`."""
    answers = _judged(quality)
    times = {k: [c.t for c in cues if c.kind == k] for k in ("blink", "clench", "turn")}
    lifts = [c for c in cues if c.kind == "lift"]
    passed_lifts = 0
    for lift in lifts:
        down = next(
            (c.t for c in cues if c.kind == "down" and c.sensor == lift.sensor and c.t > lift.t),
            lift.t + LIFT_S,
        )
        passed_lifts += _lift_passes(answers, lift, down)
    return ScoreReport(
        rules=quality.rules or RULES_VERSION,
        allowed_s=ALLOWED_S,
        blinks=kind_score(blinks_found(quality, times["blink"]), len(times["blink"])),
        clenches=kind_score(
            sum(span_found(answers, quality.tension_spans, t) for t in times["clench"]),
            len(times["clench"]),
        ),
        turns=kind_score(
            sum(span_found(answers, quality.movement_spans, t) for t in times["turn"]),
            len(times["turn"]),
        ),
        quiet=_quiet(quality, cues),
        lifts=kind_score(passed_lifts, len(lifts)),
        replay_identical=replay,
    )


def _verdict(passed: bool | None) -> str:
    return "not scored" if passed is None else "pass" if passed else "fail"


def _number(value: float | None, scale: float = 1.0, unit: str = "") -> str:
    return "not available" if value is None else f"{scale * value:.1f}{unit}"


def report_lines(report: ScoreReport) -> list[str]:
    """The score report of contracts/cli.md."""

    def kind(name: str, k: KindScore) -> str:
        if k.passed is None:
            return f"  {name:<12}  not scored (no cues)"
        return f"  {name:<12}  {k.found} of {k.total}   {_verdict(k.passed)}"

    q = report.quiet
    if q.passed is None:
        quiet = f"  {'quiet':<12}  not scored ({q.not_scored})"
    else:
        parts = [
            f"muscle activity {_number(q.tension_share, 100, '%')}",
            f"head movement {_number(q.movement_share, 100, '%')}",
            f"{_number(q.blinks_per_min_closed)} blinks per minute, eyes closed",
        ]
        quiet = f"  {'quiet':<12}  {' · '.join(parts)}   {_verdict(q.passed)}"
    replay = {None: "not checked", True: "identical to live", False: "differs from live"}
    return [
        f"Labelled session score (rules {report.rules}, a mark counts within "
        f"{report.allowed_s:.1f} s of its cue)",
        kind("blinks", report.blinks),
        kind("jaw clenches", report.clenches),
        kind("head turns", report.turns),
        quiet,
        kind("lifts", report.lifts),
        f"  {'false marks':<12}  {q.false_marks} in quiet stretches",
        f"  {'replay':<12}  {replay[report.replay_identical]}",
        f"  {'RESULT':<12}  {'pass' if report.passed else 'fail'}",
    ]
