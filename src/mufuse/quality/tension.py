"""Muscle activity in the forehead signal, one level per stretch (rules section 5).

A broadband rise between 30 and 98 Hz, with the mains (50, 60 Hz) and the Athena's own lines
(42.7, 85.3 Hz) left out. It describes the signal: muscle activity in it, never a state of the
person. Known weakness: a single loud forehead sensor that still touches the skin reads as tension.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import cache

import numpy as np
from numpy.typing import NDArray

from mufuse.acquisition.types import FloatArray
from mufuse.quality.answer import Mark
from mufuse.quality.rules import RULES, Rules


@cache
def _bins(n: int, bands: tuple[tuple[int, int], ...], skip: tuple[int, ...]) -> NDArray[np.bool_]:
    hz = np.fft.rfftfreq(n, 1.0 / n)  # a stretch is one second: bin k is k Hz
    keep = np.zeros(hz.size, dtype=bool)
    for low, high in bands:
        keep |= (hz >= low) & (hz <= high)
    keep &= ~np.isin(hz, skip)
    return keep


def tension_level(x: FloatArray, rules: Rules = RULES) -> float:
    """The µV rms of one sensor's stretch in the tension bands."""
    finite = np.isfinite(x)
    fill = float(np.mean(x[finite])) if finite.any() else 0.0
    x = np.where(finite, x, fill)  # a missing sample adds nothing
    x = x - np.mean(x)
    w = np.hanning(x.size)
    power = 2.0 * np.abs(np.fft.rfft(x * w)) ** 2 / (x.size * np.sum(w**2))
    keep = _bins(x.size, rules.tension_bands_hz, rules.tension_skip_hz)
    return float(np.sqrt(np.sum(power[keep])))


def tension(
    forehead: FloatArray, in_use: Sequence[bool], rules: Rules = RULES
) -> tuple[Mark, float | None]:
    """The mark and level of a stretch: `forehead` is (256, 2), AF7 then AF8."""
    levels = [tension_level(forehead[:, i], rules) for i, used in enumerate(in_use) if used]
    if not levels:
        return "unavailable", None
    level = min(levels)
    return ("yes" if level > rules.tension_uv else "no"), level
