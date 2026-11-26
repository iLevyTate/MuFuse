"""Optics frames that hold no data because the detectors saw too much light.

The Athena's optics are 20-bit. In bright light an ambient row sits at the ceiling (2^20 - 1),
or the headset reports every LED row as exactly 0 (seen with a lamp on the sensors in a real F1).
Such a frame is "too much light", not a measurement: it is shown and left out, never repaired.

Rows are BrainFlow's OPT1-16 in wire order (athena.py). The ambient rows OPT5-8 exist with the
16-channel presets (p1041, p1042) only; with the 4- and 8-channel presets only the ceiling is
checked. Ambient light is never subtracted here or anywhere else: the headset appears to do that
already.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from mufuse.acquisition.types import FloatArray

OPTICS_FULL_SCALE = 2**20 - 1
AMBIENT_ROWS = (4, 5, 6, 7)  # OPT5-8, 0-based, 16-channel presets
LED_ROWS = tuple(i for i in range(16) if i not in AMBIENT_ROWS)


def too_much_light(frames: FloatArray, *, sixteen_channels: bool = True) -> NDArray[np.bool_]:
    """Per frame (rows of `frames`, the 16 OPT columns): whether it saw too much light."""
    x = np.asarray(frames, dtype=np.float64)[:, :16]
    saturated = (x >= OPTICS_FULL_SCALE).any(axis=1)
    if not sixteen_channels:
        return saturated
    leds_zeroed = (x[:, LED_ROWS] == 0).all(axis=1) & (x[:, AMBIENT_ROWS] > 0).any(axis=1)
    return saturated | leds_zeroed
