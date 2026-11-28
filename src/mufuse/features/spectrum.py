"""The forehead spectrum of clean seconds: its aperiodic line, alpha peak and band shares.

The exponent is our own censored regression (003 decision 3): a straight line through log10 power
against log10 frequency, the alpha range left out, so a peak cannot bend it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from mufuse.acquisition.types import FloatArray
from mufuse.features.params import PARAMS, Params


@dataclass(frozen=True)
class AperiodicFit:
    exponent: float  # minus the slope: larger means steeper
    offset: float  # log10 power at 1 Hz on the line
    r2: float  # how well the line fits the points it was fitted to

    def at(self, freqs: FloatArray) -> FloatArray:
        """The line's log10 power at `freqs` (above 0 Hz)."""
        return self.offset - self.exponent * np.log10(freqs)


@dataclass(frozen=True)
class AlphaPeak:
    hz: float
    height: float  # log10 units above the aperiodic line


@dataclass(frozen=True)
class BandShares:
    theta: float
    alpha: float
    beta: float


def pair_spectrum(x: FloatArray, fs: float) -> tuple[FloatArray, FloatArray]:
    """One-sided power spectral density of one 2 s piece (Hann window, mean removed)."""
    y = np.asarray(x, dtype=np.float64)
    y = y - y.mean()
    w = np.hanning(y.size)
    spectrum = np.abs(np.fft.rfft(y * w)) ** 2 / (fs * float((w**2).sum()))
    spectrum[1:-1] *= 2  # the negative frequencies' share
    return np.fft.rfftfreq(y.size, d=1 / fs), spectrum


def _within(freqs: FloatArray, band: tuple[float, float]) -> np.ndarray:
    return (freqs >= band[0]) & (freqs <= band[1])


def fit_aperiodic(freqs: FloatArray, psd: FloatArray, p: Params = PARAMS) -> AperiodicFit | None:
    """The line through 2-40 Hz without 7-14 Hz; None when there is nothing to fit."""
    use = _within(freqs, p.fit_hz) & ~_within(freqs, p.alpha_hz) & (psd > 0)
    if use.sum() < 3:
        return None
    x, y = np.log10(freqs[use]), np.log10(psd[use])
    slope, offset = np.polyfit(x, y, 1)
    residual = y - (offset + slope * x)
    total = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - float((residual**2).sum()) / total if total > 0 else 0.0
    return AperiodicFit(exponent=float(-slope), offset=float(offset), r2=r2)


def alpha_peak(
    freqs: FloatArray, psd: FloatArray, fit: AperiodicFit, p: Params = PARAMS
) -> AlphaPeak | None:
    """The highest point above the line within 7-14 Hz, if it stands high enough."""
    look = _within(freqs, p.alpha_hz) & (psd > 0)
    if not look.any():
        return None
    above = np.log10(psd[look]) - fit.at(freqs[look])
    i = int(np.argmax(above))
    if above[i] < p.peak_min_log10:
        return None
    return AlphaPeak(hz=float(freqs[look][i]), height=float(above[i]))


def band_shares(freqs: FloatArray, psd: FloatArray, p: Params = PARAMS) -> BandShares:
    """Theta, alpha and beta power as shares of the 2-40 Hz power."""
    total = float(psd[_within(freqs, p.fit_hz)].sum())

    def share(band: tuple[float, float]) -> float:
        # Half-open bands, so neighbours do not count their shared edge twice.
        inside = (freqs >= band[0]) & (freqs < band[1])
        return float(psd[inside].sum()) / total if total > 0 else 0.0

    return BandShares(share(p.theta_hz), share(p.alpha_band_hz), share(p.beta_hz))
