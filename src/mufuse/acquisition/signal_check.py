"""Rough, instant per-EEG-channel indicator for the live view.

This is deliberately crude: it answers "is this electrode obviously broken right now?" so the
user can adjust the headband. Real contact-quality scoring (blink/EMG/motion aware) is feature
002. Input is ~2 s of one channel in microvolts, already DC-offset removed by the caller.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

from mufuse.acquisition.types import FloatArray

ChannelStatus = Literal["flat", "railed", "noisy", "ok"]

# Starting thresholds — tune against real Athena recordings.
FLAT_UV = 1.0  # robust spread below this: no real signal
NOISY_UV = 75.0  # robust spread above this: poor contact / EMG / movement
RAIL_UV = 1000.0  # |amplitude| above this counts as a saturated sample
RAIL_FRACTION = 0.10  # share of saturated samples that makes the window "railed"


def classify_channel(window_uv: FloatArray) -> ChannelStatus:
    """Classify one EEG channel window.

    - "flat":   almost no variation -> electrode off skin or dead channel
    - "railed": huge excursions -> amplifier saturating, electrode lifting
    - "noisy":  large but not saturated -> poor contact, jaw clench, movement
    - "ok":     plausible scalp EEG range

    Typical dry-electrode scalp EEG is tens of µV; blinks on AF7/AF8 reach ~100-200 µV.
    """
    x = np.asarray(window_uv, dtype=np.float64)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return "flat"
    if np.mean(np.abs(x) > RAIL_UV) > RAIL_FRACTION:
        return "railed"
    spread = spread_uv(x)
    if spread < FLAT_UV:
        return "flat"
    if spread > NOISY_UV:
        return "noisy"
    return "ok"


def spread_uv(window_uv: FloatArray) -> float:
    """Scaled median absolute deviation: a robust spread that brief blinks cannot inflate."""
    x = np.asarray(window_uv, dtype=np.float64)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return 0.0
    return 1.4826 * float(np.median(np.abs(x - np.median(x))))
