"""Optics frames that hold no data because the detectors saw too much light.

The Athena's optics are 20-bit. In bright light an ambient row sits at the ceiling (2^20 - 1),
or the headset reports every LED row as exactly 0 (seen with a lamp on the sensors in a real F1).
Such a frame is "too much light", not a measurement: it is shown and left out, never repaired.

Rows are BrainFlow's OPT1-16 in wire order (athena.py). The ambient rows OPT5-8 exist with the
16-channel presets (p1041, p1042) only; with the 4- and 8-channel presets only the ceiling is
checked. Ambient light is never subtracted here or anywhere else: the headset appears to do that
already.

`detector_grades` gives the live view one word per photodiode (LO, LI, RI, RO, left to right as
worn). A detector on the skin shows the heartbeat: in the 2026-11-26 sitting the strongest
0.7-3 Hz peak (and its harmonic) held 75-92% of each detector's 0.3-8 Hz power over 10 s windows
while worn, and under half off the head. Each group of four OPT rows is LI, RI, LO, RO.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from numpy.typing import NDArray

from mufuse.acquisition.types import FloatArray

OPTICS_FULL_SCALE = 2**20 - 1
AMBIENT_ROWS = (4, 5, 6, 7)  # OPT5-8, 0-based, 16-channel presets
LED_ROWS = tuple(i for i in range(16) if i not in AMBIENT_ROWS)

DetectorGrade = Literal["pulse", "finding", "light", "none"]
DETECTORS = ("LO", "LI", "RI", "RO")  # left to right as worn
_IN_GROUP = {"LI": 0, "RI": 1, "LO": 2, "RO": 3}  # position within each group of four rows
OPTICS_HZ = 64.0
PULSE_WINDOW_S = 10.0  # the heartbeat is looked for in this long
PULSE_MIN_S = 8.0  # less than this is still "finding"
PULSE_SHARE = 0.5  # share of the 0.3-8 Hz power in the heartbeat peak and its harmonic
LIGHT_S = 1.0  # glare counts when it is this recent


def too_much_light(frames: FloatArray, *, sixteen_channels: bool = True) -> NDArray[np.bool_]:
    """Per frame (rows of `frames`, the 16 OPT columns): whether it saw too much light."""
    x = np.asarray(frames, dtype=np.float64)[:, :16]
    saturated = (x >= OPTICS_FULL_SCALE).any(axis=1)
    if not sixteen_channels:
        return saturated
    leds_zeroed = (x[:, LED_ROWS] == 0).all(axis=1) & (x[:, AMBIENT_ROWS] > 0).any(axis=1)
    return saturated | leds_zeroed


def detector_grades(
    frames: FloatArray, rate: float = OPTICS_HZ, *, sixteen_channels: bool = True
) -> dict[str, DetectorGrade]:
    """One grade per detector from the last frames (rows of `frames`, the OPT columns first).

    "light": too much light reached it in the last second; "none": its LED rows never change;
    "pulse": a heartbeat stands out over the last 10 s; "finding": anything else (too little data,
    or no clear heartbeat yet). Empty for presets without the 16-row layout.
    """
    if not sixteen_channels:
        return {}
    x = np.asarray(frames, dtype=np.float64)[:, :16]
    x = x[-int(PULSE_WINDOW_S * rate) :]
    recent = x[-int(LIGHT_S * rate) :]
    grades: dict[str, DetectorGrade] = {}
    for name in DETECTORS:
        k = _IN_GROUP[name]
        leds = [k, 8 + k, 12 + k]  # red, 730 nm, 850 nm
        ambient = 4 + k
        if not x.shape[0]:
            grades[name] = "finding"
        elif (recent[:, ambient] >= OPTICS_FULL_SCALE).any() or (
            (recent[:, leds] == 0).all(axis=1) & (recent[:, ambient] > 0)
        ).any():
            grades[name] = "light"
        elif bool((np.ptp(x[:, leds], axis=0) == 0).all()):
            grades[name] = "none"
        elif x.shape[0] < PULSE_MIN_S * rate:
            grades[name] = "finding"
        else:
            share = max(pulse_share(x[:, row], rate) for row in leds)
            grades[name] = "pulse" if share >= PULSE_SHARE else "finding"
    return grades


def pulse_share(x: FloatArray, rate: float = OPTICS_HZ) -> float:
    """Share of the 0.3-8 Hz power within 0.15 Hz of the strongest 0.7-3 Hz peak or its harmonic."""
    y = np.asarray(x, dtype=np.float64)
    t = np.arange(y.size)
    y = y - np.polyval(np.polyfit(t, y, 1), t)
    power = np.abs(np.fft.rfft(y * np.hanning(y.size))) ** 2
    freqs = np.fft.rfftfreq(y.size, d=1 / rate)
    counted = (freqs >= 0.3) & (freqs <= 8.0)
    total = float(power[counted].sum())
    if total <= 0:
        return 0.0
    beat = (freqs >= 0.7) & (freqs <= 3.0)
    peak = float(freqs[int(np.argmax(np.where(beat, power, 0.0)))])
    near = (np.abs(freqs - peak) <= 0.15) | (np.abs(freqs - 2 * peak) <= 0.15)
    return float(power[counted & near].sum()) / total
