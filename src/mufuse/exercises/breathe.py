"""Paced breathing (009): the guided session and what it measured, from the recording.

Two minutes sitting quietly, then N minutes of paced breathing (6 a minute by default), then two
minutes quietly again. The primary measure is the peak-to-trough swing of the beat interval within
each breath-length window (max minus min interval, median over windows): at 64 Hz it is measured
far better than RMSSD, which reads high (specs/003-eeg-ppg-features, "What was found"). Every
phase is cut into windows of the same length, so the phases are measured the same way. Beat
intervals that touch a second judged as moving (002) are left out, and each phase says how long
that was. The result describes the signal; it says nothing about health.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from mufuse.acquisition.optics import LED_ROWS, OPTICS_HZ
from mufuse.acquisition.simulated import Wearer
from mufuse.acquisition.types import StreamKind
from mufuse.features.pulse import beat_times, combined, plausible, rmssd_ms
from mufuse.guide import Cue, Guide

if TYPE_CHECKING:
    from mufuse.quality.answer import SessionQuality, Span
    from mufuse.recording.reader import LoadedSession

QUIET_S = 120.0  # before and after
DEFAULT_RATE = 6.0  # breaths a minute
DEFAULT_MINUTES = 5.0
MIN_PHASE_S = 30.0
MIN_WINDOW_BEATS = 3  # intervals a window needs for a swing
REACT_S = 0.4  # the rehearsal's wearer follows a cue this late
QUIET_RSA = (15.0, 30.0)  # the rehearsal's wearer at rest: breaths a minute, swing ms
PACED_SWING_MS = 150.0  # ... and while pacing (a modest swing for six a minute)

PHASES = ("before", "pace", "after")


@dataclass(frozen=True)
class Schedule:
    rate: float
    minutes: float

    @property
    def period(self) -> float:
        return 60.0 / self.rate

    @property
    def pace_s(self) -> float:
        return QUIET_S

    @property
    def after_s(self) -> float:
        return QUIET_S + 60.0 * self.minutes

    @property
    def end_s(self) -> float:
        return self.after_s + QUIET_S


def breathe_guide(rate: float = DEFAULT_RATE, minutes: float = DEFAULT_MINUTES) -> Guide:
    if not 3.0 <= rate <= 12.0:
        raise ValueError("--rate must be between 3 and 12 breaths a minute")
    if not 1.0 <= minutes <= 30.0:
        raise ValueError("--minutes must be between 1 and 30")
    s = Schedule(rate, minutes)
    cues = [Cue(0.0, "Sit quietly and breathe as usual", "b:before")]
    cues.append(Cue(s.pace_s, f"Paced breathing, {rate:g} a minute: follow the cues", "b:pace"))
    breaths = round(60.0 * minutes / s.period)
    for k in range(breaths):
        at = s.pace_s + k * s.period
        cues.append(Cue(at, f"Breathe in ({k + 1} of {breaths})", step=False))
        cues.append(Cue(at + s.period / 2, f"Breathe out ({k + 1} of {breaths})", step=False))
    cues.append(Cue(s.after_s, "Sit quietly and breathe as usual", "b:after"))
    cues.append(Cue(s.end_s, "Done. Saving and measuring", "b:end"))
    title = f"Paced breathing · {rate:g} a minute for {minutes:g} min (009)"
    return Guide(cues=tuple(cues), duration=s.end_s + 2.0, title=title)


def rehearsal_wearer(
    rate: float = DEFAULT_RATE, minutes: float = DEFAULT_MINUTES, react_s: float = REACT_S
) -> Wearer:
    """A simulated wearer who follows the pacing `react_s` late (breathing shows in the pulse)."""
    s = Schedule(rate, minutes)
    quiet_rate, quiet_swing = QUIET_RSA
    return Wearer(
        rsa=(
            (0.0, s.pace_s + react_s, quiet_rate, quiet_swing),
            (s.pace_s + react_s, s.after_s + react_s, rate, PACED_SWING_MS),
            (s.after_s + react_s, s.end_s + 10.0, quiet_rate, quiet_swing),
        )
    )


@dataclass(frozen=True)
class Phase:
    name: str
    seconds: float
    hr_bpm: float | None
    swing_ms: float | None  # median peak-to-trough swing of the beat interval per window
    rmssd_ms: float | None  # experimental at 64 Hz
    windows: int  # breath-length windows with a swing
    moving_s: float = 0.0  # seconds judged as moving (002), their beat intervals left out


@dataclass(frozen=True)
class BreatheReport:
    rate: float
    phases: dict[str, Phase]

    def raised(self, measure: str) -> bool | None:
        """Whether `measure` ("swing_ms" or "rmssd_ms") was higher while pacing than before."""
        before = getattr(self.phases["before"], measure)
        pace = getattr(self.phases["pace"], measure)
        return None if before is None or pace is None else bool(pace > before)


def _ms(x: float | None) -> str:
    return "-" if x is None else f"{x:.0f} ms"


def report_lines(r: BreatheReport) -> list[str]:
    before, pace = r.phases["before"], r.phases["pace"]
    lines = [f"Paced breathing at {r.rate:g} a minute (breathing 1)"]
    for p in r.phases.values():
        hr = "-" if p.hr_bpm is None else f"{p.hr_bpm:.0f} bpm"
        lines.append(
            f"  {p.name:<7} {p.seconds:5.0f} s  heart rate {hr:>8}  swing {_ms(p.swing_ms):>7}"
            f" ({p.windows} windows)  RMSSD {_ms(p.rmssd_ms):>7} (experimental)"
            + (f"  {p.moving_s:.0f} s moving left out" if p.moving_s > 0 else "")
        )
    if pace.swing_ms is None or before.swing_ms is None:
        lines.append("Not measured: too little pulse signal in a phase.")
        return lines
    lines.append(
        f"During paced breathing the beat-interval swing was {pace.swing_ms:.0f} ms against"
        f" {before.swing_ms:.0f} ms before (RMSSD {_ms(before.rmssd_ms)} → {_ms(pace.rmssd_ms)},"
        " experimental)."
    )
    for measure, name in (("swing_ms", "swing"), ("rmssd_ms", "RMSSD")):
        raised = r.raised(measure)
        word = "not known" if raised is None else ("raised" if raised else "not raised")
        lines.append(f"  {name:<6} vs before: {word}")
    return lines


def still(beats: np.ndarray, moving: Sequence[Span]) -> np.ndarray:
    """For each interval between `beats`, whether it touches no moving span."""
    keep = np.ones(max(beats.size - 1, 0), dtype=bool)
    for span in moving:
        keep &= (beats[1:] <= span.start) | (beats[:-1] >= span.end)
    return keep


def _overlap(lo: float, hi: float, moving: Sequence[Span]) -> float:
    return sum(max(0.0, min(hi, s.end) - max(lo, s.start)) for s in moving)


def phase_measure(
    name: str, t: np.ndarray, x: np.ndarray, period: float, moving: Sequence[Span] = ()
) -> Phase:
    """Heart rate, swing and RMSSD of one phase's optics frames (`x`: rows by OPT column),
    leaving out beat intervals that touch a `moving` span."""
    seconds = float(t[-1] - t[0]) if t.size else 0.0
    moving_s = _overlap(float(t[0]), float(t[-1]), moving) if t.size else 0.0
    empty = Phase(name, seconds, None, None, None, 0, moving_s)
    if seconds < MIN_PHASE_S:
        return empty
    sixteen = x.shape[1] - 1 == 16
    rows = list(LED_ROWS if sixteen else range(x.shape[1] - 1))
    wave = combined(x[:, rows], OPTICS_HZ)
    if wave is None:
        return empty
    beats = beat_times(wave, OPTICS_HZ) + float(t[0])
    if beats.size < 4:
        return empty
    intervals = np.diff(beats)
    calm = still(beats, moving)
    kept = plausible(intervals) & calm
    ends = beats[1:]
    swings: list[float] = []
    for k in range(int(seconds // period)):
        lo = float(t[0]) + k * period
        inside = kept & (ends >= lo) & (ends < lo + period)
        if int(inside.sum()) >= MIN_WINDOW_BEATS:
            swings.append(float(np.ptp(intervals[inside])))
    hr = 60.0 / float(np.median(intervals[kept])) if int(kept.sum()) >= 2 else None
    swing = 1000.0 * float(np.median(swings)) if swings else None
    # NaN, not removed: neighbours across a moving span must not count as successive
    rmssd = rmssd_ms(np.where(calm, intervals, np.nan))
    return Phase(name, seconds, hr, swing, rmssd, len(swings), moving_s)


def measure(
    session: LoadedSession, rate: float = DEFAULT_RATE, quality: SessionQuality | None = None
) -> BreatheReport | None:
    """The report of a recorded breathe session; None when its markers are not all there.
    `quality` is the session judged by 002 (judged here when not given)."""
    at = {m.label: m.t for m in session.markers if m.label.startswith("b:")}
    if not all(k in at for k in ("b:before", "b:pace", "b:after", "b:end")):
        return None
    ts, data = session.streams.get(StreamKind.OPTICS, (np.empty(0), np.empty((0, 17))))
    edges = {
        "before": (at["b:before"], at["b:pace"]),
        "pace": (at["b:pace"], at["b:after"]),
        "after": (at["b:after"], at["b:end"]),
    }
    if quality is None:
        from mufuse.quality.engine import judge

        quality = judge(session)
    period = 60.0 / rate
    phases: dict[str, Phase] = {}
    for name in PHASES:
        lo, hi = edges[name]
        keep = (ts >= lo) & (ts < hi)
        phases[name] = phase_measure(name, ts[keep], data[keep], period, quality.movement_spans)
    return BreatheReport(rate, phases)
