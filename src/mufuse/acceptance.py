"""Guided hardware acceptance for 001 (tests/hardware/README.md): preflight P0, H8, H6, H7, H5,
F1, then H4.

Each check is a guided recording: what to read before starting, timed on-screen cues, and an
automatic verdict computed from the saved session. Cue times are seconds after streaming starts,
and verdicts use the same schedule against the session's `started_at`, so anyone re-running the
checks gets the same instructions and the same pass rules.

Every judge also files the numbers behind its verdict in `Result.measures`, so a check that
failed can be judged again later from what was saved, without the headband.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from mufuse.acquisition.athena import ATHENA_STREAMS, preset_warning
from mufuse.acquisition.optics import too_much_light
from mufuse.acquisition.signal_check import FULL_SCALE_UV, NOISY_UV, classify_channel, spread_uv
from mufuse.acquisition.simulated import CTRL_C, Wearer
from mufuse.acquisition.types import FloatArray, StreamKind
from mufuse.guide import READY_S, Cue, Guide, action
from mufuse.recording.format import Gap, ReconnectWhat
from mufuse.recording.reader import LoadedSession


@dataclass(frozen=True)
class Result:
    check: str
    passed: bool
    lines: tuple[str, ...]
    measures: dict[str, float] = field(default_factory=dict[str, float])


@dataclass
class _Report:
    lines: list[str] = field(default_factory=list[str])
    passed: bool = True
    measures: dict[str, float] = field(default_factory=dict[str, float])

    def check(self, ok: bool, text: str) -> None:
        self.passed &= ok
        self.lines.append(f"[{'ok' if ok else 'FAIL'}] {text}")

    def info(self, text: str) -> None:
        self.lines.append(f"[info] {text}")

    def measure(self, name: str, value: float) -> None:
        self.measures[name] = round(float(value), 4)


EARLY_S = 5.0  # a recording this much shorter than its check was stopped by hand


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
        ts, _ = _eeg(session)
        ended: float | None = session.manifest.get("ended_at")
        length = 0.0 if ended is None else float(ended) - _t0(session)
        if ts.size == 0:
            report.check(
                False,
                "no samples were recorded at all: the connection was made but nothing arrived; "
                "retry",
            )
        elif self.id != "H7" and ended is not None and length < self.duration - EARLY_S:
            # H7 asks for the stop. Anywhere else the cues after it were never shown.
            report.check(
                False,
                f"the recording was stopped after {length:.0f} s of {self.duration:.0f} s "
                "(q or Ctrl+C): retry",
            )
        self._judge(self, session, report)
        # The battery level is the last optics column; it reads 0 until the headband reports it.
        _, optics = session.streams.get(StreamKind.OPTICS, (np.empty(0), np.empty((0, 17))))
        reported = optics[optics[:, -1] > 0, -1]
        if reported.size:
            report.measure("battery_end_pct", reported[-1])
        return Result(self.id, report.passed, tuple(report.lines), report.measures)


def _t0(session: LoadedSession) -> float:
    return float(session.manifest["started_at"])


def _eeg(session: LoadedSession) -> tuple[np.ndarray, np.ndarray]:
    return session.streams.get(StreamKind.EEG, (np.empty(0), np.empty((0, 4))))


def _gap_text(gap: Gap, t0: float) -> str:
    length = "still open at the end" if gap.end is None else f"for {gap.end - gap.start:.1f} s"
    return f"gap at +{gap.start - t0:.1f} s {length} ({gap.reason})"


# Completeness: H4 / SC-002, and the preflight ----------------------------------------------

COMPLETE_PCT = 99.5
# Samples in one subpacket of each stream on presets p1041/p1042 (BrainFlow's muse_athena.cpp).
SUBPACKET_SAMPLES = {"eeg": 2, "motion": 3, "optics": 1}


def _completeness(session: LoadedSession, r: _Report) -> dict[str, tuple[int, int, float]]:
    """Per stream: samples expected over its span, samples received, and the effective rate."""
    streams: dict[str, tuple[int, int, float]] = {}
    counts: dict[str, dict[str, int]] = session.manifest.get("completeness") or {}
    for kind, c in counts.items():
        expected, received = int(c["expected"]), int(c["received"])
        nominal = float(session.manifest["streams"][kind]["sampling_rate"])
        rate = nominal * (received - 1) / (expected - 1) if expected > 1 else 0.0
        streams[kind] = (expected, received, rate)
        r.measure(f"{kind}.completeness_pct", _pct(expected, received))
        r.measure(f"{kind}.rate_hz", rate)
    return streams


def _pct(expected: int, received: int) -> float:
    return 100 * received / expected if expected else 0.0


def _judge_h4(check: Check, session: LoadedSession, r: _Report) -> None:
    ts, _ = _eeg(session)
    span = float(ts[-1] - ts[0]) if ts.size > 1 else 0.0
    r.check(
        span >= check.duration - 10, f"recorded {span:.0f} s (need ≥ {check.duration - 10:.0f} s)"
    )
    streams = _completeness(session, r)
    r.check(bool(streams), "session finalized with completeness counts")
    lost: dict[str, int] | None = session.manifest.get("lost_subpackets")
    short: list[str] = []  # streams under the limit
    pc_side: list[str] = []  # ... that would still be under it with the headset's loss added back
    for kind, (expected, received, rate) in streams.items():
        pct = _pct(expected, received)
        r.check(
            pct >= COMPLETE_PCT,
            f"{kind} {pct:.2f}% complete (need ≥ {COMPLETE_PCT:.2f}%) · {rate:.2f} Hz effective",
        )
        missing = max(expected - received, 0)
        subpackets = lost.get(kind, 0) if lost is not None else 0
        headset = min(subpackets * SUBPACKET_SAMPLES.get(kind, 1), missing)
        r.measure(f"{kind}.missing", missing)
        r.measure(f"{kind}.lost_on_headset", headset)
        r.measure(f"{kind}.lost_on_pc", missing - headset)
        if lost is None:
            r.info(f"{kind}: {missing} of {expected} samples missing (no headset loss counter)")
        else:
            r.info(
                f"{kind}: {missing} of {expected} samples missing: {headset} lost on the headset "
                f"link ({subpackets} subpackets by its counter), {missing - headset} on the PC side"
            )
        if pct < COMPLETE_PCT:
            short.append(kind)
            if _pct(expected, received + headset) < COMPLETE_PCT:
                pc_side.append(kind)
    if short and not pc_side:
        r.info(
            f"{', '.join(short)} failed only through samples the headband never sent: the PC "
            "kept everything that arrived. The headset's counter is not yet verified on hardware."
        )
        r.info(
            "whether loss on the headset counts against SC-002 is a decision for the spec; "
            "as written it does, so this stays a FAIL"
        )
    r.info(f"gaps recorded: {len(session.gaps)}")
    for gap in session.gaps:
        r.info(_gap_text(gap, _t0(session)))
    # Not judged: the long recording's own numbers, for tuning the channel check (feature 002).
    # Windows side by side: a quarter of the work on ten minutes.
    whole = _phase(session, 0.0, span, step=WINDOW_S)
    _describe(r, "whole", "over the whole recording", whole)


# H5 / SC-003 -------------------------------------------------------------------------------

RESUME_LIMIT_S = 20.0
OFF_LATE_S = 8.0  # holding the power button takes a moment
# A real off-and-on cannot be shorter: 3 s until the stall is noticed, 1 s of backoff, and
# 4-6 s to connect again.
MIN_GAP_S = 8.0
_STEP: dict[ReconnectWhat, str] = {
    "lost": "the signal counted as lost",
    "released": "the old connection was let go",
    "attempt": "an attempt to connect began",
    "failed": "that attempt failed",
    "connected": "connected",
    "first_sample": "the first sample arrived",
}


def _judge_h5(check: Check, session: LoadedSession, r: _Report) -> None:
    _h5_rules(check, session, r)
    # Where the time away went, as the recorder's supervisor saw it: not judged.
    t0, on = _t0(session), check.at("power_on")
    for step in session.reconnects:
        at = step.t - t0
        detail = f" ({step.detail})" if step.detail else ""
        r.info(
            f"reconnect +{at:.1f} s ({at - on:+.1f} s from the power-on cue): "
            f"{_STEP[step.what]}{detail}"
        )


def _h5_rules(check: Check, session: LoadedSession, r: _Report) -> None:
    t0 = _t0(session)
    off, on = check.at("power_off"), check.at("power_on")
    at_cue = [g for g in session.gaps if -READY_S <= g.start - t0 - off <= OFF_LATE_S]
    gap = at_cue[0] if at_cue else None
    for other in session.gaps:
        if other is not gap:
            r.info("other " + _gap_text(other, t0))
    r.measure("gaps", len(session.gaps))
    if gap is None:
        if session.gaps:
            r.check(
                False,
                f"no interruption started near the power-off cue "
                f"(need {-READY_S:+.0f} to {OFF_LATE_S:+.0f} s from it)",
            )
        else:
            r.check(False, "no interruption was seen at all: the signal never stopped")
        return
    stopped = gap.start - t0
    r.measure("stopped_offset_s", stopped - off)
    r.check(True, f"signal stopped {stopped - off:+.1f} s from the power-off cue")
    ended = float(session.manifest.get("ended_at") or t0 + check.duration) - t0
    if gap.end is None:
        r.check(
            False,
            f"the headband never came back (open gap from +{stopped:.1f} s): the recording "
            f"ended at +{ended:.1f} s, {ended - on:.1f} s after the power-on cue",
        )
        return
    back, length = gap.end - t0, gap.end - gap.start
    r.measure("gap_s", length)
    r.measure("resume_s", back - on)
    r.check(
        length >= MIN_GAP_S,
        f"signal was away for {length:.1f} s (need ≥ {MIN_GAP_S:.0f} s: "
        "a real off-and-on cannot be shorter)",
    )
    r.check(
        back - on <= RESUME_LIMIT_S + READY_S,
        f"streaming resumed {abs(back - on):.1f} s {'before' if back < on else 'after'} the "
        f"power-on cue (need ≤ {RESUME_LIMIT_S:.0f} s after it, +{READY_S:.0f} s tolerance)",
    )
    if back < on:
        r.info(
            "the signal was back before the power-on cue: an early switch-on is not held "
            "against the check, the time away still has to be long enough"
        )
    ts, _ = _eeg(session)
    inside = (ts[:-1] >= gap.start - 1.0) & (ts[1:] <= gap.end + 1.0)
    hole = float(np.diff(ts)[inside].max()) if inside.any() else 0.0
    r.measure("hole_s", hole)
    r.check(
        abs(hole - length) <= 0.5,
        f"recorded gap {length:.2f} s vs hole in the EEG data {hole:.2f} s (need within ±0.5 s)",
    )
    r.info(
        f"timeline: off cue +{off:.0f} s · signal stopped +{stopped:.1f} s · on cue +{on:.0f} s "
        f"· signal back +{back:.1f} s · recording ended +{ended:.1f} s · reason {gap.reason}"
    )


# H6 / SC-004 -------------------------------------------------------------------------------

PRESS_LATE_S = 5.0


def _judge_h6(check: Check, session: LoadedSession, r: _Report) -> None:
    t0 = _t0(session)
    presses = [m.t - t0 for m in session.markers if m.source == "keyboard" and m.kind == "moment"]
    unused = sorted(presses)
    # SC-004 is about where a marker sits in time, so each cue is judged by the first press in
    # its window. A double tap or a stray press is reported and not held against the check.
    for i, at in enumerate((c.at for c in check.cues if c.marker), 1):
        first = next((p for p in unused if at - READY_S <= p <= at + PRESS_LATE_S), None)
        if first is None:
            r.check(False, f"press {i}: none in its window")
        else:
            unused.remove(first)
            r.measure(f"press_{i}.offset_s", first - at)
            r.check(True, f"press {i}: {first - at:+.1f} s from its cue")
    r.measure("presses", len(presses))
    extra = "".join(f"  +{p:.1f} s" for p in unused)
    r.info(f"{len(presses)} SPACE markers, {len(unused)} extra (not counted){extra}")


# H7 / SC-005 -------------------------------------------------------------------------------

STOP_LATE_S = 10.0


def _judge_h7(check: Check, session: LoadedSession, r: _Report) -> None:
    r.check(session.finalized, "session reloads as finalized after Ctrl+C")
    ts, _ = _eeg(session)
    r.measure("eeg_samples", ts.size)
    r.check(ts.size > 0, f"{ts.size} EEG samples saved")
    ended = session.manifest.get("ended_at")
    if ended is None:
        return
    stopped = float(ended) - (_t0(session) + check.at("ctrl_c"))
    r.measure("stopped_offset_s", stopped)
    r.check(
        -READY_S <= stopped <= STOP_LATE_S,
        f"stopped {stopped:+.1f} s from the Ctrl+C cue (need within {STOP_LATE_S:.0f} s, "
        "so it was Ctrl+C and not the time limit)",
    )


# EEG phases: H8 and the preflight ----------------------------------------------------------
# The live indicator (`classify_channel`) grades a centred window by a robust spread, which a
# disturbance shorter than a quarter of the window cannot move: in real Athena data an input
# without skin contact shows a sharp dip every 12 samples and still reads "ok". The judges
# therefore compare plain numbers against the wearer's own rest phase, and print the indicator's
# labels as [info] for tuning it later (feature 002).

SETTLE_S = 2.0  # ignore the start of each phase: people react at different speeds
WINDOW_S, STEP_S = 2.0, 0.5  # same window the live view classifies
_CHANNELS = ATHENA_STREAMS[StreamKind.EEG].channel_names[:4]
_SENSOR = {"TP9": "left ear", "AF7": "left forehead", "AF8": "right forehead", "TP10": "right ear"}
_EEG_HZ = ATHENA_STREAMS[StreamKind.EEG].sampling_rate
EEG_RANGE_UV = FULL_SCALE_UV  # the amplifier ends there: (raw - 8192) * 1450 / 16383
RAIL_MARGIN = 0.05  # a sample this close to either end of the range counts as railed
RAIL_SHARE = 0.10  # share of railed samples that makes a window railed
FLAT_PTP_UV = 2.0  # peak-to-peak below this: no signal at all
CHANGE_FACTOR = 3.0  # a window changed when its std is this many times the rest std
REST_FLOOR_UV = 5.0  # ... and the rest std counts as at least this
MAINS_HZ = (50, 60)
LABELS = ("ok", "noisy", "flat", "railed")  # what the live indicator can call a window
DEFLECTION_FACTOR = 5.0  # blink-like: this many rest spreads away from the phase's median


@dataclass(frozen=True)
class _Phase:
    """One cue phase of the four EEG channels, cut into the live view's windows.

    `std`, `ptp`, `spread` and `rail` are (windows, 4). `rail` is the share of samples near
    either end of the amplifier's range, taken before centring. `mains` is (2, 4): the share of
    the phase's power above 1 Hz that lies within 1 Hz of 50 and of 60 Hz.
    """

    samples: FloatArray
    std: FloatArray
    ptp: FloatArray
    spread: FloatArray
    rail: FloatArray
    labels: tuple[tuple[str, ...], ...]
    mains: FloatArray

    @property
    def windows(self) -> int:
        return int(self.std.shape[0])


def _phase(session: LoadedSession, start: float, end: float, step: float = STEP_S) -> _Phase:
    """The EEG over [start + settle, end) seconds after the recording started."""
    ts, data = _eeg(session)
    t0 = _t0(session)
    wins: list[FloatArray] = []
    a = t0 + start + SETTLE_S
    while a + WINDOW_S <= t0 + end:
        win = data[(ts >= a) & (ts < a + WINDOW_S), :4]
        if win.shape[0] >= WINDOW_S * _EEG_HZ / 2:  # at most half of it missing
            wins.append(win)
        a += step
    samples = data[(ts >= t0 + start + SETTLE_S) & (ts < t0 + end), :4]
    centred = [w - w.mean(axis=0) for w in wins]
    near_rail = (1 - RAIL_MARGIN) * EEG_RANGE_UV
    mains = np.zeros((2, 4))
    if samples.shape[0] >= _EEG_HZ:
        power = np.abs(np.fft.rfft(samples - samples.mean(axis=0), axis=0)) ** 2
        freqs = np.fft.rfftfreq(samples.shape[0], d=1 / _EEG_HZ)
        total = np.maximum(power[freqs >= 1.0].sum(axis=0), 1e-12)
        mains = np.array([power[np.abs(freqs - hz) <= 1.0].sum(axis=0) / total for hz in MAINS_HZ])
    return _Phase(
        samples=samples,
        std=np.array([w.std(axis=0) for w in wins]).reshape(-1, 4),
        ptp=np.array([np.ptp(w, axis=0) for w in wins]).reshape(-1, 4),
        spread=np.array([[spread_uv(c[:, i]) for i in range(4)] for c in centred]).reshape(-1, 4),
        rail=np.array([(np.abs(w) >= near_rail).mean(axis=0) for w in wins]).reshape(-1, 4),
        labels=tuple(tuple(classify_channel(c[:, i]) for i in range(4)) for c in centred),
        mains=mains,
    )


def _describe(r: _Report, name: str, title: str, p: _Phase) -> None:
    """File the phase's numbers per channel and print them with the indicator's label shares."""
    if not p.windows:
        r.info(f"{title}: no EEG recorded")
        return
    std, spread, ptp = (np.median(v, axis=0) for v in (p.std, p.spread, p.ptp))
    low, high = np.percentile(p.spread, (5, 95), axis=0)
    rail = p.rail.mean(axis=0)
    labels: list[str] = []
    for i, ch in enumerate(_CHANNELS):
        r.measure(f"{name}.{ch}.std_uv", std[i])
        r.measure(f"{name}.{ch}.spread_uv", spread[i])
        r.measure(f"{name}.{ch}.spread_p05_uv", low[i])
        r.measure(f"{name}.{ch}.spread_p95_uv", high[i])
        r.measure(f"{name}.{ch}.ptp_uv", ptp[i])
        r.measure(f"{name}.{ch}.rail_share", rail[i])
        for hz, share in zip(MAINS_HZ, p.mains[:, i], strict=True):
            r.measure(f"{name}.{ch}.mains_{hz}hz_share", share)
        seen = [row[i] for row in p.labels]
        shares = {label: seen.count(label) / len(seen) for label in dict.fromkeys(seen)}
        for label in LABELS:
            r.measure(f"{name}.{ch}.{label}_share", shares.get(label, 0.0))
        labels.append(f"{ch} " + " ".join(f"{label} {s:.0%}" for label, s in shares.items()))
    numbers = "  ".join(
        f"{ch} {std[i]:.0f}/{spread[i]:.0f}/{ptp[i]:.0f}" for i, ch in enumerate(_CHANNELS)
    )
    r.info(f"{title}: std/robust spread/peak-to-peak in µV: {numbers}")
    r.info(f"labels {title}: " + " · ".join(labels))


def _mains(r: _Report, title: str, p: _Phase) -> None:
    """Print how much of the baseline is mains hum, the usual reason for a noisy rest."""
    shares = "  ".join(
        f"{ch} {'/'.join(f'{s:.0%}' for s in p.mains[:, i])}" for i, ch in enumerate(_CHANNELS)
    )
    r.info(f"{title}: share of power at {'/'.join(map(str, MAINS_HZ))} Hz (mains): {shares}")


def _deflections(x: FloatArray, level: float) -> tuple[int, float]:
    """Excursions further than `level` from the median, 0.3 s or more apart: count, median peak."""
    away = np.abs(x - np.median(x))
    idx = np.flatnonzero(away > level)
    if idx.size == 0:
        return 0, 0.0
    groups = np.split(idx, np.flatnonzero(np.diff(idx) > 0.3 * _EEG_HZ) + 1)
    return len(groups), float(np.median([away[g].max() for g in groups]))


def _judge_h8(check: Check, session: LoadedSession, r: _Report) -> None:
    rest = _phase(session, check.at("relax"), check.at("lift_tp9"))
    lift = _phase(session, check.at("lift_tp9"), check.at("replace"))
    clench = _phase(session, check.at("clench"), check.at("relax_jaw"))
    blink = _phase(session, check.at("blink"), check.at("end"))
    phases = {"rest": rest, "lift": lift, "clench": clench, "blink": blink}
    for name, p in phases.items():
        _describe(r, name, "at rest" if name == "rest" else f"during {name}", p)
    _mains(r, "at rest", rest)
    if not all(p.windows for p in phases.values()):
        r.check(False, "EEG recorded in all four phases")
        return
    rest_std = np.maximum(np.median(rest.std, axis=0), REST_FLOOR_UV)

    def changed(p: _Phase) -> FloatArray:
        """Per channel, the share of windows that no longer look like the rest phase."""
        loud = p.std >= CHANGE_FACTOR * rest_std
        return (loud | (p.ptp < FLAT_PTP_UV) | (p.rail > RAIL_SHARE)).mean(axis=0)

    lifted, resting = changed(lift), changed(rest)
    lift_std = np.median(lift.std, axis=0)
    for i, ch in enumerate(_CHANNELS):
        r.measure(f"lift.{ch}.changed_share", lifted[i])
        r.measure(f"rest.{ch}.changed_share", resting[i])
    r.check(
        lifted[0] >= 0.5,
        f"lifting the left ear sensor changed TP9 in {lifted[0]:.0%} of windows (need ≥ 50%): "
        f"std {lift_std[0]:.0f} µV against {rest_std[0]:.0f} µV at rest",
    )
    r.check(
        resting[0] < 0.5,
        f"TP9 was steady at rest: it looked lifted in {resting[0]:.0%} of rest windows "
        "(need < 50%)",
    )
    most = int(np.lexsort((lift_std / rest_std, lifted))[-1])
    if lifted[most] == 0:
        r.info("no channel changed while lifting")
    else:
        r.info(
            f"changed most while lifting: {_CHANNELS[most]} ({_SENSOR[_CHANNELS[most]]}) "
            f"in {lifted[most]:.0%} of windows"
        )
        if most != 0:
            r.info(
                "if the left ear sensor was the one lifted, left and right are swapped in the "
                "recording; otherwise a different sensor was lifted"
            )

    # Std over the whole phase, so a clench that comes in bursts or ends early still counts.
    jaw = np.sqrt((clench.std**2).mean(axis=0)) / rest_std
    r.measure("clench.TP9.std_ratio", jaw[0])
    r.measure("clench.TP10.std_ratio", jaw[3])
    r.check(
        max(jaw[0], jaw[3]) >= CHANGE_FACTOR,
        f"jaw clench raised the std to {jaw[0]:.1f} times rest on TP9 and {jaw[3]:.1f} times "
        f"on TP10 (need ≥ {CHANGE_FACTOR:.0f} times on either)",
    )

    lost = ((blink.ptp < FLAT_PTP_UV) | (blink.rail > RAIL_SHARE)).mean(axis=0)
    worst = int(np.argmax(lost))
    r.check(
        lost[worst] < 0.5,
        f"while blinking no channel went flat or railed: {_CHANNELS[worst]} did in "
        f"{lost[worst]:.0%} of windows (need < 50%)",
    )
    found: list[str] = []
    for i in (1, 2):
        level = DEFLECTION_FACTOR * max(float(np.median(rest.spread[:, i])), REST_FLOOR_UV)
        count, peak = _deflections(blink.samples[:, i], level)
        r.measure(f"blink.{_CHANNELS[i]}.deflections", count)
        r.measure(f"blink.{_CHANNELS[i]}.deflection_uv", peak)
        found.append(f"{_CHANNELS[i]} {count} (median {peak:.0f} µV)")
    r.info(f"blink-like deflections: {'  '.join(found)}; about one a second was asked for")


# P0: preflight -----------------------------------------------------------------------------

# Judged on the level as the headset reports it. Since the battery row is corrected (BrainFlow
# reads half of it, see athena_status.py) 20% is about two hours of use, plenty for the half-hour
# sitting. Sessions recorded before the correction saved half the level, so for them 20% was 40%.
BATTERY_MIN_PCT = 20.0
STREAM_MIN_PCT = 95.0
FIT_OK_SHARE = 0.8
# The last firmware with public evidence of unchanged sensor placement and output.
FIRMWARE_KNOWN = (3, 1, 29)


def _judge_p0(check: Check, session: LoadedSession, r: _Report) -> None:
    firmware: str | None = session.manifest["device"].get("firmware")
    if firmware is None:
        r.info("firmware was not reported by the headband")
    elif tuple(int(n) for n in re.findall(r"\d+", firmware)) > FIRMWARE_KNOWN:
        known = ".".join(map(str, FIRMWARE_KNOWN))
        r.info(
            f"firmware {firmware} is newer than {known}, the last version with public evidence "
            "of unchanged sensor placement and output"
        )
    else:
        r.info(f"firmware {firmware}")
    extra: dict[str, str] = session.manifest["device"].get("extra") or {}
    warning = preset_warning(session.manifest["device"]["preset"], extra.get("active_preset"))
    if warning is not None:
        r.info(warning)

    # The battery level is the last optics column. It reads 0 for the first seconds.
    _, optics = session.streams.get(StreamKind.OPTICS, (np.empty(0), np.empty((0, 17))))
    battery = float(optics[:, -1].max()) if optics.shape[0] else 0.0
    if battery > 0:
        r.measure("battery_pct", battery)
        r.check(
            battery >= BATTERY_MIN_PCT,
            f"battery {battery:.0f}% (need ≥ {BATTERY_MIN_PCT:.0f}%; if lower, "
            "charge first: the full sitting takes about half an hour)",
        )
    else:
        r.info("battery level was not reported; check the charge another way before the long run")

    streams = _completeness(session, r)
    r.check(bool(streams), "session finalized with completeness counts")
    for kind, (expected, received, rate) in streams.items():
        pct = _pct(expected, received)
        r.check(
            pct >= STREAM_MIN_PCT,
            f"{kind} {pct:.2f}% of its nominal rate (need ≥ {STREAM_MIN_PCT:.0f}%) "
            f"· {rate:.2f} Hz effective",
        )
        if STREAM_MIN_PCT <= pct < COMPLETE_PCT:
            r.info(f"{kind} is under {COMPLETE_PCT}%: H4 is at risk; move closer to the PC")

    still = _phase(session, check.at("still"), check.duration)
    _describe(r, "still", "while still", still)
    _mains(r, "while still", still)
    if not still.windows:
        r.check(False, "EEG recorded while sitting still")
        return
    # The label alone cannot see a sensor without contact (see above), so the quietest quarter
    # of the windows must also stay under the indicator's own noise limit by plain std.
    quiet = np.percentile(still.std, 25, axis=0)
    for i, ch in enumerate(_CHANNELS):
        ok = sum(row[i] == "ok" for row in still.labels) / still.windows
        r.check(
            ok >= FIT_OK_SHARE and quiet[i] <= NOISY_UV,
            f"{ch} ({_SENSOR[ch]}) ok in {ok:.0%} of still windows (need ≥ {FIT_OK_SHARE:.0%}), "
            f"quietest windows {quiet[i]:.0f} µV (need ≤ {NOISY_UV:.0f} µV); "
            "if not, reseat that sensor on the skin",
        )


# F1: optics ambient channels ---------------------------------------------------------------
# BrainFlow board 67 passes optics through in wire order: OPT1-4 red, 5-8 ambient, 9-12 730 nm,
# 13-16 850 nm, each group LI, RI, LO, RO. libMuse (and Mind Monitor) reorder to OPTICS1-16 with
# ambient at 11, 12, 15, 16. docs/research/2026-11-25-athena-fnirs-resources.md, update 2026-11-26.
#
# In real data the ambient rows sit on a pedestal near 338 000 counts whatever the light, so they
# never fall "close to zero" when covered. What marks them: covered, they read the same as on the
# head (both dark), and room light lifts them above that level. LED rows read something else on
# the head, where their own light comes back from the skin.

AMBIENT_WIRE: tuple[int, ...] = (5, 6, 7, 8)
AMBIENT_LIBMUSE: tuple[int, ...] = (11, 12, 15, 16)
CARDIAC_HZ = (0.7, 3.0)
PEDESTAL_MATCH = 0.10  # covered level within this share of the on-head level
LIGHT_RISE = 1000.0  # counts room light must add over the covered level (noise is about 40)
_F1_PHASES = (
    ("on_head", "room_light", "on head"),
    ("room_light", "dark", "room light"),
    ("dark", "light_again", "covered"),
    ("light_again", "end", "light again"),
)


def _optics_window(session: LoadedSession, start: float, end: float) -> FloatArray:
    """The 16 OPT rows over [start + settle, end)."""
    ts, data = session.streams[StreamKind.OPTICS]
    t0 = _t0(session)
    return data[(ts >= t0 + start + SETTLE_S) & (ts < t0 + end), :16]


def _pulsatility(win: FloatArray) -> FloatArray:
    """Share of each channel's 0.1-10 Hz power that sits in the cardiac band."""
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


def _opt(rows: tuple[int, ...]) -> str:
    return f"OPT{', OPT'.join(map(str, rows))}"


def _judge_f1(check: Check, session: LoadedSession, r: _Report) -> None:
    if StreamKind.OPTICS not in session.streams:
        r.check(False, "no optics stream in this session (use preset p1041 or p1042)")
        return
    windows = [_optics_window(session, check.at(a), check.at(b)) for a, b, _ in _F1_PHASES]
    if not all(w.shape[0] for w in windows):
        r.check(False, "optics recorded in all four phases")
        return
    levels = [np.median(w, axis=0) for w in windows]
    for (name, _, title), level in zip(_F1_PHASES, levels, strict=True):
        for i, value in enumerate(level):
            r.measure(f"{name}.OPT{i + 1}.median", value)
        r.info(f"{title}: " + "  ".join(f"{i + 1}:{v:.0f}" for i, v in enumerate(level)))
    for (name, _, title), win in zip(_F1_PHASES, windows, strict=True):
        glare = float(too_much_light(win).mean())
        r.measure(f"{name}.too_much_light_share", glare)
        if glare:
            r.info(
                f"{title}: too much light in {glare:.0%} of optics frames (an ambient row at the "
                "20-bit ceiling, or every LED row at 0): those frames hold no data"
            )
    head, light_1, dark, light_2 = levels
    _, all_rows = session.streams[StreamKind.OPTICS]
    if not np.ptp(all_rows[:, :16], axis=0).any():
        r.check(False, "optics stream is flat; check the preset and reconnect")
        return

    lit = np.minimum(light_1, light_2)
    steady = np.abs(head - dark) <= PEDESTAL_MATCH * np.maximum(np.maximum(head, dark), 1.0)
    ambient = _rows(np.flatnonzero(steady & (lit - dark >= LIGHT_RISE)))
    for n in range(1, 17):
        r.measure(f"ambient.OPT{n}", n in ambient)
    for title, diff in (
        ("room light over covered", lit - dark),
        ("covered over on head", dark - head),
    ):
        r.info(f"{title}: " + "  ".join(f"{i + 1}:{d:.0f}" for i, d in enumerate(diff)))
    if not ambient:
        # Nothing qualified. Say why before the order verdict: one light phase that never got
        # its light, room light too dim for both, or a cover that let light through.
        rose = float((lit - head).max())
        short = _light_phase_short(steady, head, light_1, light_2)
        if short is not None:
            r.check(False, short)
        elif rose < LIGHT_RISE:
            r.check(
                False,
                f"room light too dim: the rows rose only about {max(round(rose, -1), 0):.0f} "
                f"counts over their on-head level (need ≥ {LIGHT_RISE:.0f}); hold the sensors "
                "off the head and face a lamp or a window",
            )
        else:
            r.check(
                False,
                "the cover let light through: rows that rose in room light did not come back "
                "to their on-head level when covered; cover the sensors completely",
            )
    # The two known orders differ in where the ambient rows are, so wire order is confirmed when
    # all of OPT5-8 behave as ambient and none of libMuse's ambient rows does. Another row that
    # does too (a weak LED row near its offset can pick up room light) is reported, not judged.
    wire = set(AMBIENT_WIRE) <= set(ambient) and not set(AMBIENT_LIBMUSE) & set(ambient)
    also = () if not wire else tuple(n for n in ambient if n not in AMBIENT_WIRE)
    shown = tuple(n for n in ambient if n not in also)
    known = {AMBIENT_WIRE: "BrainFlow wire order", AMBIENT_LIBMUSE: "libMuse order"}
    named = _opt(shown) if shown else "no row"
    r.check(
        wire,
        f"ambient light shows on {named}: {known.get(shown, 'neither known order')} "
        "(expected OPT5-8 for BrainFlow wire order, and none of OPT11, 12, 15, 16). Ambient rows "
        f"read the same covered as on the head (within {PEDESTAL_MATCH:.0%}) and rise "
        f"≥ {LIGHT_RISE:.0f} counts in room light",
    )
    if also:
        r.info(
            f"{_opt(also)} also behaved as ambient light: not held against the check, since no "
            "known order puts ambient light there"
        )
    pulse = _pulsatility(windows[0])
    for i, share in enumerate(pulse):
        r.measure(f"on_head.OPT{i + 1}.pulse_share", share)
    weakest = _rows(np.argsort(pulse)[:4])
    r.info(f"least pulse on the head: {_opt(weakest)} (ambient channels should carry no heartbeat)")


def _light_phase_short(
    steady: np.ndarray, head: FloatArray, light_1: FloatArray, light_2: FloatArray
) -> str | None:
    """When the room light lifted the steady rows in one light phase and not in the other, what
    to say about the phase that fell short. None when both or neither rose."""
    if not steady.any():
        return None
    rose_1, rose_2 = (
        float((light - head)[steady].max()) >= LIGHT_RISE for light in (light_1, light_2)
    )
    if rose_1 and not rose_2:
        return (
            "the 'light again' phase stayed at the covered level: uncover the sensors and face "
            "the light until it says done"
        )
    if rose_2 and not rose_1:
        return (
            "the 'room light' phase stayed at the on-head level: take the headband off and hold "
            "the sensors facing a lamp or a window until told to cover them"
        )
    return None


# The checks -----------------------------------------------------------------------------------

# The recorder saves first and then lets go of the headband, which takes several seconds.
_RELEASE = (
    "When the time is up, wait for the verdict: the release of the headband takes up to 10 s."
)


def _h6_cues() -> tuple[Cue, ...]:
    cues = [Cue(0, "Keep still")]
    for i, at in enumerate((10.0, 18.0, 26.0), 1):
        cues += action(at, f"Press SPACE ({i} of 3)", marker=f"space_{i}")
        cues.append(Cue(at + 3, "Done pressing, keep still" if i == 3 else "Wait for the next cue"))
    return tuple(cues)


# In running order: the preflight, then everything that needs hands, and the ten hands-free
# minutes last. F1 takes the headband off, so it comes after the checks that need it worn.
CHECKS: dict[str, Check] = {
    c.id: c
    for c in (
        Check(
            "P0",
            "Preflight: fit, battery and streams",
            (
                "Put the headband on. Close the Muse phone app.",
                "First 15 s: adjust the headband until all four sensors show ok.",
                "Then sit still for 30 s, eyes open, jaw relaxed.",
                _RELEASE,
            ),
            45.0,
            (
                Cue(0, "Adjust the headband until all four sensors show ok", marker="adjust"),
                *action(15, "Sit still, eyes open, jaw relaxed", marker="still"),
            ),
            _judge_p0,
        ),
        Check(
            "H8",
            "Channel check reacts to contact, jaw and blinks",
            (
                "The LEFT ear sensor sits behind your left ear (TP9).",
                "You'll be asked to: sit still, lift that sensor off your skin, let it go back,",
                "clench your jaw, relax it, then blink about once a second.",
                _RELEASE,
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
            "H6",
            "Keyboard markers (SC-004)",
            (
                "Keep this terminal window focused: SPACE only registers here.",
                "Press SPACE once each time you're told; there are 3 presses.",
                _RELEASE,
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
                "When told, tap Ctrl+C once, do not hold it, and do not click in the window.",
                "If text gets highlighted, press Esc first: a selection takes the Ctrl+C.",
                "The recording should still save properly.",
                _RELEASE,
            ),
            60.0,
            (
                Cue(0, "Keep still"),
                *action(15, "Tap Ctrl+C once", marker="ctrl_c"),
                Cue(18, "Tap Ctrl+C once if you haven't yet"),
            ),
            _judge_h7,
        ),
        Check(
            "H5",
            "Power-cycle recovery (SC-003)",
            (
                "Put a finger on the headband's power button now so you can find it blind.",
                "When told, turn the headband OFF, keep it off about 10 s, then turn it ON.",
                "Stay seated with the headband on; it reconnects by itself.",
                "The screen may freeze for up to 15 s while it searches for the headband; "
                "press nothing.",
                _RELEASE,
            ),
            75.0,
            (
                Cue(0, "Keep still, headband on"),
                *action(20, "Turn the headband OFF", marker="power_off"),
                Cue(23, "Keep it OFF"),
                *action(30, "Turn the headband ON", marker="power_on"),
                Cue(33, "Press nothing while it reconnects (should take under 20 s)"),
            ),
            _judge_h5,
        ),
        Check(
            "F1",
            "fNIRS optics: which channels are ambient light",
            (
                "The optical sensors are in the middle of the forehead strip.",
                "Have a dark cloth ready, or plan to cup your hand tightly over the sensors.",
                "You'll sit still wearing it, then hold it off your head with the sensors facing "
                "a lamp or a window.",
                "Then cover the sensors completely, then uncover them.",
                "Keep the headband switched on throughout.",
                _RELEASE,
            ),
            98.0,
            (
                Cue(0, "Sit still with the headband on", marker="on_head"),
                *action(
                    30,
                    "Take the headband off; hold the forehead sensors facing a lamp or a window",
                    marker="room_light",
                ),
                *action(55, "Cover the forehead sensors completely and hold", marker="dark"),
                *action(80, "Uncover the sensors, facing the light again", marker="light_again"),
                Cue(95, "Done, you can put the headband back on", marker="end"),
            ),
            _judge_f1,
        ),
        Check(
            "H4",
            "10-minute recording completeness (SC-002)",
            (
                "The headband may be worn or lie switched on within 2 m of the PC.",
                "There is nothing to do for 10 minutes; leave the keyboard alone.",
                _RELEASE,
            ),
            600.0,
            (Cue(0, "Nothing to do: leave the headband switched on within 2 m of the PC"),),
            _judge_h4,
        ),
    )
}


# Rehearsal: a simulated wearer for each check ---------------------------------------------

BOOT_S = 3.0  # from the power button to a headband that can be found: a guess, not measured


def wearer_for(check: Check, *, react: float = 1.0, idle: bool = False) -> Wearer:
    """The script of a simulated wearer who does what `check` asks, `react` seconds after each
    cue. An idle wearer keeps the headband on and does nothing at all."""
    if idle:
        return Wearer()

    def at(label: str) -> float:
        return check.at(label) + react

    if check.id == "P0":  # still adjusting until told to sit still
        return Wearer(lifted=((0.0, at("still"), "TP9"),))
    if check.id == "H8":
        return Wearer(
            lifted=((at("lift_tp9"), at("replace"), "TP9"),),
            clench=((at("clench"), at("relax_jaw")),),
            blinks=((at("blink"), at("end")),),
        )
    if check.id == "H6":
        return Wearer(keys=tuple((c.at + react, " ") for c in check.cues if c.marker))
    if check.id == "H7":
        return Wearer(keys=((at("ctrl_c"), CTRL_C),))
    if check.id == "H5":
        return Wearer(off=((at("power_off"), at("power_on") + BOOT_S),))
    if check.id == "F1":
        return Wearer(
            optics=(
                (at("room_light"), "light"),
                (at("dark"), "covered"),
                (at("light_again"), "light"),
            )
        )
    return Wearer()  # H4: nothing to do


def wearer_from_env() -> Wearer | None:
    """The simulated wearer chosen in MUFUSE_SIM_WEARER, if any: a check id for a wearer who
    follows that check, or the id and ":idle" for one who does nothing."""
    raw = os.environ.get("MUFUSE_SIM_WEARER", "").strip()
    if not raw:
        return None
    check_id, _, variant = raw.upper().partition(":")
    if check_id not in CHECKS or variant not in ("", "IDLE"):
        raise ValueError(
            f"MUFUSE_SIM_WEARER={raw!r} is not a rehearsal. Use one of {', '.join(CHECKS)}, "
            "or add :idle for a wearer who does nothing, e.g. H8:idle"
        )
    return wearer_for(CHECKS[check_id], idle=variant == "IDLE")
