"""Per-sensor contact grade for the live view, from the last second of raw EEG (issue #13).

A fitting aid, not the signal-quality model (that is feature 002). Each of TP9, AF7, AF8 and
TP10 gets one of three grades from its last 1 s of samples, before any centring:

- "none" (no contact): flat; or railed (more than 10% of the samples within 2% of the ±725 µV
  full scale); or loud and mostly mains hum (at least 60% of the power above 1 Hz within 1 Hz
  of 50 or 60 Hz). A sensor off the skin reads like that: in the 2026-11-26 sitting 100-550 µV
  with 85-100% of its power at 60 Hz, or pinned at full scale. One more signature, not seen on
  our unit but in the public muse-rs capture (firmware 3.1.19) that the simulator copies: a
  floating input with a deep dip every 12 samples, quiet by robust spread but loud by plain
  standard deviation, nearly all of it on the Athena's own period-12 lines.
- "noisy" (touching but noisy): louder than the channel check's limit (a robust spread above
  75 µV) without being mostly hum: movement, jaw, a loose fit (under 25% at 60 Hz there).
- "good": at or under that limit. Good contact carries a lot of hum too (80-98% of its power
  there), which is why the hum share only counts once a sensor is loud.

The Athena adds 1-3 µV lines at 21.3, 42.7 and 64 Hz (a pattern every 12 samples) in every
preset; they are left out of the hum share.

The hold (a sensor shows "settling" until it has been good for three judged seconds in a row,
while a worse grade shows at once) lives in the quality engine, `mufuse.quality.engine`, which
grades each second with `grade_window`. Grades describe the signal, never the person, and their
colours grade signal quality only (docs/BRAND.md).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.signal_check import FLAT_UV, NOISY_UV, RAIL_FRACTION, RAIL_UV, spread_uv
from mufuse.acquisition.types import FloatArray, StreamKind

Grade = Literal["none", "noisy", "good"]
Why = Literal["flat", "railed", "hum", "floating", "loud", "quiet"]
Shown = Literal["waiting", "none", "noisy", "settling", "good"]

SENSORS = ATHENA_STREAMS[StreamKind.EEG].channel_names[:4]
EEG_HZ = ATHENA_STREAMS[StreamKind.EEG].sampling_rate
WINDOW_S = 1.0
MAINS_HZ = (50.0, 60.0)
MAINS_SHARE = 0.60  # a loud sensor with at least this share of hum is not touching the skin
INTERFERENCE_HZ = (EEG_HZ / 12, 2 * EEG_HZ / 12, 64.0)  # the Athena's own 21.3, 42.7, 64 Hz
PATTERN_HZ = tuple(k * EEG_HZ / 12 for k in range(1, 7))  # those lines and their harmonics
LINE_HZ = 1.0  # half-width of a mains or interference band
_FOREHEAD = ("AF7", "AF8")


@dataclass(frozen=True)
class Reading:
    grade: Grade
    why: Why
    spread_uv: float  # robust spread of the window
    mains_share: float  # share of the power above 1 Hz at 50 or 60 Hz, interference left out


@dataclass(frozen=True)
class SensorView:
    name: str
    shown: Shown
    reading: Reading | None
    settle_left_s: int = 0  # whole seconds until a settling sensor shows as good


def grade_window(window_uv: FloatArray, rate: float = EEG_HZ) -> Reading | None:
    """Grade one sensor's last second of raw samples; None when there is too little of it."""
    x = np.asarray(window_uv, dtype=np.float64)
    x = x[np.isfinite(x)]
    if x.size < WINDOW_S * rate / 2:
        return None
    spread = spread_uv(x)
    mains = mains_share(x, rate)
    if np.mean(np.abs(x) >= RAIL_UV) > RAIL_FRACTION:
        return Reading("none", "railed", spread, mains)
    if spread < FLAT_UV:
        return Reading("none", "flat", spread, mains)
    if spread <= NOISY_UV:
        if float(x.std()) > NOISY_UV and _share(x, PATTERN_HZ, rate) >= MAINS_SHARE:
            return Reading("none", "floating", spread, mains)
        return Reading("good", "quiet", spread, mains)
    if mains >= MAINS_SHARE:
        return Reading("none", "hum", spread, mains)
    return Reading("noisy", "loud", spread, mains)


def mains_share(x: FloatArray, rate: float = EEG_HZ) -> float:
    """Share of the power above 1 Hz within 1 Hz of 50 or 60 Hz, the Athena's lines left out."""
    return _share(x, MAINS_HZ, rate, leave_out=INTERFERENCE_HZ)


def _share(
    x: FloatArray, lines: Sequence[float], rate: float, leave_out: Sequence[float] = ()
) -> float:
    """Share of the power above 1 Hz that lies within 1 Hz of `lines`, `leave_out` not counted."""
    centred = x - x.mean()
    power = np.abs(np.fft.rfft(centred * np.hanning(centred.size))) ** 2
    freqs = np.fft.rfftfreq(centred.size, d=1 / rate)
    counted = (freqs >= 1.0) & ~_near(freqs, leave_out)
    total = float(power[counted].sum())
    return float(power[counted & _near(freqs, lines)].sum()) / total if total > 0 else 0.0


def _near(freqs: FloatArray, lines: Sequence[float]) -> np.ndarray:
    near = np.zeros(freqs.size, dtype=bool)
    for hz in lines:
        near |= np.abs(freqs - hz) <= LINE_HZ
    return near


_RANK: dict[Shown, int] = {"none": 3, "noisy": 2, "settling": 1, "good": 0, "waiting": 0}


def tip(views: Sequence[SensorView]) -> str | None:
    """One thing to try, for the sensor whose signal needs it most (the first of equals)."""
    worst = max(views, key=lambda v: _RANK[v.shown], default=None)
    if worst is None or _RANK[worst.shown] == 0:
        return None
    if worst.shown == "none":
        if worst.name in _FOREHEAD:
            return f"{worst.name}: push hair off the forehead, wet the skin under the sensor"
        return f"{worst.name}: push hair aside, wet the skin behind the ear"
    if worst.shown == "noisy":
        return f"{worst.name}: hold still, relax your jaw"
    return f"{worst.name}: hold still while the signal settles"
