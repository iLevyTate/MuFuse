"""Guided hardware acceptance for 001 (tests/hardware/README.md, H4-H8).

Each check is a guided recording: what to read before starting, timed on-screen cues, and an
automatic verdict computed from the saved session. Cue times are seconds after streaming starts,
and verdicts use the same schedule against the session's `started_at`, so anyone re-running the
checks gets the same instructions and the same pass rules.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.signal_check import classify_channel, spread_uv
from mufuse.acquisition.types import StreamKind
from mufuse.guide import READY_S, Cue, Guide, action
from mufuse.recording.reader import LoadedSession


@dataclass(frozen=True)
class Result:
    check: str
    passed: bool
    lines: tuple[str, ...]


@dataclass
class _Report:
    lines: list[str] = field(default_factory=list[str])
    passed: bool = True

    def check(self, ok: bool, text: str) -> None:
        self.passed &= ok
        self.lines.append(f"[{'ok' if ok else 'FAIL'}] {text}")

    def info(self, text: str) -> None:
        self.lines.append(f"[info] {text}")


@dataclass(frozen=True)
class Check:
    id: str
    title: str
    before: tuple[str, ...]  # read out before the recording starts
    duration: float  # recording stops by itself after this many seconds
    cues: tuple[Cue, ...]
    _judge: Callable[[Check, LoadedSession, _Report], None]

    def guide(self) -> Guide:
        return Guide(cues=self.cues, duration=self.duration, title=f"{self.id} · {self.title}")

    def at(self, label: str) -> float:
        """Scheduled offset of the cue that writes marker `label`."""
        return next(c.at for c in self.cues if c.marker == label)

    def evaluate(self, session: LoadedSession) -> Result:
        report = _Report()
        self._judge(self, session, report)
        return Result(self.id, report.passed, tuple(report.lines))


def _t0(session: LoadedSession) -> float:
    return float(session.manifest["started_at"])


def _eeg(session: LoadedSession) -> tuple[np.ndarray, np.ndarray]:
    return session.streams.get(StreamKind.EEG, (np.empty(0), np.empty((0, 4))))


# H4 / SC-002 -------------------------------------------------------------------------------


def _judge_h4(check: Check, session: LoadedSession, r: _Report) -> None:
    ts, _ = _eeg(session)
    span = float(ts[-1] - ts[0]) if ts.size > 1 else 0.0
    r.check(
        span >= check.duration - 10, f"recorded {span:.0f} s (need ≥ {check.duration - 10:.0f} s)"
    )
    completeness: dict[str, dict[str, int]] = session.manifest.get("completeness") or {}
    r.check(bool(completeness), "session finalized with completeness counts")
    for kind, c in completeness.items():
        pct = 100 * c["received"] / c["expected"] if c["expected"] else 0.0
        r.check(pct >= 99.5, f"{kind} {pct:.2f}% complete (need ≥ 99.50%)")
    r.info(f"gaps recorded: {len(session.gaps)}")


# H5 / SC-003 -------------------------------------------------------------------------------

RESUME_LIMIT_S = 20.0
OFF_LATE_S = 8.0  # holding the power button takes a moment


def _judge_h5(check: Check, session: LoadedSession, r: _Report) -> None:
    t0 = _t0(session)
    off, on = t0 + check.at("power_off"), t0 + check.at("power_on")
    closed = [g for g in session.gaps if g.end is not None]
    open_gaps = len(session.gaps) - len(closed)
    r.check(bool(closed), "a gap was recorded and closed (the headband went off and came back)")
    if not closed:
        r.info(f"open gaps: {open_gaps}")
        return
    gap = max(closed, key=lambda g: (g.end or g.start) - g.start)
    assert gap.end is not None
    resumed = gap.end - on
    r.check(
        resumed <= RESUME_LIMIT_S + READY_S,
        f"streaming resumed {resumed:.1f} s after the power-on cue "
        f"(need ≤ {RESUME_LIMIT_S:.0f} s, +{READY_S:.0f} s tolerance)",
    )
    stopped = gap.start - off
    r.check(
        -READY_S <= stopped <= OFF_LATE_S,
        f"signal stopped {stopped:+.1f} s from the power-off cue "
        f"(need {-READY_S:+.0f} to {OFF_LATE_S:+.0f} s)",
    )
    ts, _ = _eeg(session)
    hole = float(np.max(np.diff(ts))) if ts.size > 1 else 0.0
    recorded = gap.end - gap.start
    r.check(
        abs(hole - recorded) <= 0.5,
        f"recorded gap {recorded:.2f} s vs hole in the EEG data {hole:.2f} s (need within ±0.5 s)",
    )
    r.info(f"gaps: {len(closed)} closed, {open_gaps} open; reason {gap.reason}")


# H6 / SC-004 -------------------------------------------------------------------------------

PRESS_LATE_S = 5.0


def _judge_h6(check: Check, session: LoadedSession, r: _Report) -> None:
    t0 = _t0(session)
    presses = [m.t - t0 for m in session.markers if m.source == "keyboard" and m.kind == "moment"]
    cue_times = [c.at for c in check.cues if c.marker]
    r.check(len(presses) == len(cue_times), f"{len(presses)} SPACE markers (need {len(cue_times)})")
    for i, at in enumerate(cue_times, 1):
        near = [p for p in presses if at - READY_S <= p <= at + PRESS_LATE_S]
        took = f"{near[0] - at:+.1f} s from its cue" if near else "none in its window"
        r.check(bool(near), f"press {i}: {took}")


# H7 / SC-005 -------------------------------------------------------------------------------

STOP_LATE_S = 10.0


def _judge_h7(check: Check, session: LoadedSession, r: _Report) -> None:
    r.check(session.finalized, "session reloads as finalized after Ctrl+C")
    ts, _ = _eeg(session)
    r.check(ts.size > 0, f"{ts.size} EEG samples saved")
    ended = session.manifest.get("ended_at")
    if ended is None:
        return
    stopped = float(ended) - (_t0(session) + check.at("ctrl_c"))
    r.check(
        -READY_S <= stopped <= STOP_LATE_S,
        f"stopped {stopped:+.1f} s from the Ctrl+C cue (need within {STOP_LATE_S:.0f} s, "
        "so it was Ctrl+C and not the time limit)",
    )


# H8 -----------------------------------------------------------------------------------------

SETTLE_S = 2.0  # ignore the start of each phase: people react at different speeds
WINDOW_S, STEP_S = 2.0, 0.5  # same window the live view classifies
_CHANNELS = ATHENA_STREAMS[StreamKind.EEG].channel_names[:4]


def _phase(
    session: LoadedSession, start: float, end: float
) -> tuple[list[dict[str, str]], list[float]]:
    """Per-window channel statuses and per-channel median spread over [start + settle, end)."""
    ts, data = _eeg(session)
    t0 = _t0(session)
    statuses: list[dict[str, str]] = []
    spreads: list[list[float]] = [[] for _ in _CHANNELS]
    a = t0 + start + SETTLE_S
    while a + WINDOW_S <= t0 + end:
        win = data[(ts >= a) & (ts < a + WINDOW_S)]
        if win.shape[0]:
            row: dict[str, str] = {}
            for i, name in enumerate(_CHANNELS):
                x = win[:, i] - win[:, i].mean()
                row[name] = classify_channel(x)
                spreads[i].append(spread_uv(x))
            statuses.append(row)
        a += STEP_S
    return statuses, [float(np.median(s)) if s else 0.0 for s in spreads]


def _share(statuses: list[dict[str, str]], channel: str, wanted: set[str]) -> float:
    return sum(s[channel] in wanted for s in statuses) / len(statuses) if statuses else 0.0


def _judge_h8(check: Check, session: LoadedSession, r: _Report) -> None:
    def phase(label: str, until: str) -> tuple[list[dict[str, str]], str]:
        statuses, spreads = _phase(session, check.at(label), check.at(until))
        text = "  ".join(f"{n} {s:.0f} µV" for n, s in zip(_CHANNELS, spreads, strict=True))
        return statuses, text

    relax, spreads = phase("relax", "lift_tp9")
    ok_share = min(_share(relax, ch, {"ok"}) for ch in _CHANNELS)
    r.info(f"at rest: every channel ok in ≥ {ok_share:.0%} of windows · spread {spreads}")

    lift, spreads = phase("lift_tp9", "replace")
    share = _share(lift, "TP9", {"flat", "railed"})
    r.check(share >= 0.5, f"lifted TP9 shows flat/railed in {share:.0%} of windows · {spreads}")

    clench, spreads = phase("clench", "relax_jaw")
    share = max(_share(clench, ch, {"noisy"}) for ch in ("TP9", "TP10"))
    r.check(share >= 0.5, f"jaw clench shows noisy on TP9/TP10 in {share:.0%} · {spreads}")

    blink, spreads = phase("blink", "end")
    share = min(_share(blink, ch, {"ok"}) for ch in _CHANNELS)
    r.check(share >= 0.5, f"while blinking every channel stays ok in ≥ {share:.0%} · {spreads}")


# F1: optics ambient channels ---------------------------------------------------------------
# BrainFlow board 67 passes optics through in wire order: OPT1-4 red, 5-8 ambient, 9-12 730 nm,
# 13-16 850 nm, each group LI, RI, LO, RO. libMuse (and Mind Monitor) reorder to OPTICS1-16 with
# ambient at 11, 12, 15, 16. docs/research/2026-11-25-athena-fnirs-resources.md, update 2026-11-26.

AMBIENT_WIRE: tuple[int, ...] = (5, 6, 7, 8)
AMBIENT_LIBMUSE: tuple[int, ...] = (11, 12, 15, 16)
CARDIAC_HZ = (0.7, 3.0)
DARK_DROP = 0.5  # ambient channels should fall close to zero when covered


def _optics_level(session: LoadedSession, start: float, end: float) -> np.ndarray:
    """Median of each OPT channel over [start + settle, end)."""
    ts, data = session.streams[StreamKind.OPTICS]
    t0 = _t0(session)
    win = data[(ts >= t0 + start + SETTLE_S) & (ts < t0 + end), :16]
    return np.median(win, axis=0) if win.shape[0] else np.zeros(16)


def _pulsatility(session: LoadedSession, start: float, end: float) -> np.ndarray:
    """Share of each channel's 0.1-10 Hz power that sits in the cardiac band."""
    ts, data = session.streams[StreamKind.OPTICS]
    t0 = _t0(session)
    win = data[(ts >= t0 + start + SETTLE_S) & (ts < t0 + end), :16]
    if win.shape[0] < 64:
        return np.zeros(16)
    x = win - win.mean(axis=0)
    power = np.abs(np.fft.rfft(x, axis=0)) ** 2
    freqs = np.fft.rfftfreq(x.shape[0], d=1 / ATHENA_STREAMS[StreamKind.OPTICS].sampling_rate)
    band = (freqs >= CARDIAC_HZ[0]) & (freqs <= CARDIAC_HZ[1])
    total = (freqs >= 0.1) & (freqs <= 10.0)
    return power[band].sum(axis=0) / np.maximum(power[total].sum(axis=0), 1e-12)


def _rows(indices: np.ndarray) -> tuple[int, ...]:
    return tuple(sorted(int(i) + 1 for i in indices))


def _judge_f1(check: Check, session: LoadedSession, r: _Report) -> None:
    if StreamKind.OPTICS not in session.streams:
        r.check(False, "no optics stream in this session (use preset p1041 or p1042)")
        return
    light = (
        _optics_level(session, check.at("room_light"), check.at("dark"))
        + _optics_level(session, check.at("light_again"), check.at("end"))
    ) / 2
    dark = _optics_level(session, check.at("dark"), check.at("light_again"))
    drop = (light - dark) / np.maximum(np.abs(light), 1e-9)
    top = np.argsort(-drop)[:4]
    ambient = _rows(top)
    darkened = float(drop[top].min())
    r.check(
        darkened >= DARK_DROP,
        f"covering darkened the sensors: the 4 most affected channels fell ≥ {darkened:.0%} "
        f"(need ≥ {DARK_DROP:.0%}; if not, cover them fully and retry)",
    )
    known = {AMBIENT_WIRE: "BrainFlow wire order", AMBIENT_LIBMUSE: "libMuse order"}
    order = known.get(ambient, "neither known order")
    r.check(
        ambient == AMBIENT_WIRE,
        f"darkness hits OPT{', OPT'.join(map(str, ambient))} hardest: {order} "
        f"(expected OPT5-8 for BrainFlow wire order)",
    )
    r.info("drop in darkness: " + "  ".join(f"{i + 1}:{d:.0%}" for i, d in enumerate(drop)))
    pulse = _pulsatility(session, check.at("on_head"), check.at("room_light"))
    weakest = _rows(np.argsort(pulse)[:4])
    r.info(
        f"least pulse on the head: OPT{', OPT'.join(map(str, weakest))} "
        f"(ambient channels should carry no heartbeat)"
    )


# The checks -----------------------------------------------------------------------------------


def _h6_cues() -> tuple[Cue, ...]:
    cues = [Cue(0, "Keep still")]
    for i, at in enumerate((10.0, 18.0, 26.0), 1):
        cues += action(at, f"Press SPACE ({i} of 3)", marker=f"space_{i}")
        cues.append(Cue(at + 3, "Done pressing, keep still" if i == 3 else "Wait for the next cue"))
    return tuple(cues)


CHECKS: dict[str, Check] = {
    c.id: c
    for c in (
        Check(
            "H4",
            "10-minute recording completeness (SC-002)",
            (
                "Charge the headband to at least 25% first.",
                "Sit within 2 m of the PC. You only need to sit still for 10 minutes.",
                "Keep your jaw relaxed; don't talk or walk away.",
            ),
            600.0,
            (Cue(0, "Sit still, jaw relaxed, eyes open"),),
            _judge_h4,
        ),
        Check(
            "H5",
            "Power-cycle recovery (SC-003)",
            (
                "Put a finger on the headband's power button now so you can find it blind.",
                "When told, turn the headband OFF, keep it off about 10 s, then turn it ON.",
                "Stay seated with the headband on; it reconnects by itself.",
            ),
            75.0,
            (
                Cue(0, "Keep still, headband on"),
                *action(20, "Turn the headband OFF", marker="power_off"),
                Cue(23, "Keep it OFF"),
                *action(30, "Turn the headband ON", marker="power_on"),
                Cue(33, "Keep still while it reconnects (should take under 20 s)"),
            ),
            _judge_h5,
        ),
        Check(
            "H6",
            "Keyboard markers (SC-004)",
            (
                "Keep this terminal window focused: SPACE only registers here.",
                "Press SPACE once each time you're told; there are 3 presses.",
            ),
            40.0,
            _h6_cues(),
            _judge_h6,
        ),
        Check(
            "H7",
            "Ctrl+C mid-recording leaves a readable session (SC-005)",
            (
                "Keep this terminal window focused.",
                "Press Ctrl+C once when told. The recording should still save properly.",
            ),
            60.0,
            (
                Cue(0, "Keep still"),
                *action(15, "Press Ctrl+C", marker="ctrl_c"),
                Cue(18, "Press Ctrl+C if you haven't yet"),
            ),
            _judge_h7,
        ),
        Check(
            "H8",
            "Channel check reacts to contact, jaw and blinks",
            (
                "The LEFT ear sensor sits behind your left ear (TP9).",
                "You'll be asked to: sit still, lift that sensor off your skin, let it go back,",
                "clench your jaw, relax it, then blink about once a second.",
            ),
            63.0,
            (
                Cue(0, "Sit still, eyes open, jaw relaxed", marker="relax"),
                *action(15, "Lift the LEFT ear sensor off your skin and hold", marker="lift_tp9"),
                *action(25, "Let the ear sensor go back onto your skin", marker="replace"),
                *action(35, "Clench your jaw firmly and hold", marker="clench"),
                *action(43, "Relax your jaw", marker="relax_jaw"),
                *action(50, "Blink about once a second", marker="blink"),
                Cue(60, "Done, keep still", marker="end"),
            ),
            _judge_h8,
        ),
        Check(
            "F1",
            "fNIRS optics: which channels are ambient light",
            (
                "The optical sensors are in the middle of the forehead strip.",
                "Have a dark cloth ready, or plan to cup your hand tightly over the sensors.",
                "You'll sit still wearing it, then hold it off your head facing the room light.",
                "Then cover the sensors completely, then uncover them.",
                "Keep the headband switched on throughout.",
            ),
            98.0,
            (
                Cue(0, "Sit still with the headband on", marker="on_head"),
                *action(
                    30,
                    "Take the headband off; hold the forehead sensors facing the room light",
                    marker="room_light",
                ),
                *action(55, "Cover the forehead sensors completely and hold", marker="dark"),
                *action(
                    80, "Uncover the sensors, facing the room light again", marker="light_again"
                ),
                Cue(95, "Done, you can put the headband back on", marker="end"),
            ),
            _judge_f1,
        ),
    )
}
