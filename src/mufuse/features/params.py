"""Features v1: every constant the 003 features depend on, in one place.

The reasons are in `specs/003-eeg-ppg-features/README.md` (decisions 1-10). A change here that
changes a frame for the reference recording is a new features version.
"""

from __future__ import annotations

from dataclasses import dataclass

FEATURES_VERSION = "1"


@dataclass(frozen=True)
class Params:
    version: str = FEATURES_VERSION

    # Spectrum (decisions 2-5)
    pair_n: int = 512  # two 1 s stretches at 256 Hz: 0.5 Hz bins
    spectrum_window_s: float = 8.0  # a frame averages the pairs that end in the last 8 s
    spectrum_min_pairs: int = 2
    fit_hz: tuple[float, float] = (2.0, 40.0)
    alpha_hz: tuple[float, float] = (7.0, 14.0)  # left out of the fit; where the peak is looked for
    peak_min_log10: float = 0.1
    theta_hz: tuple[float, float] = (4.0, 8.0)
    alpha_band_hz: tuple[float, float] = (8.0, 13.0)
    beta_hz: tuple[float, float] = (13.0, 30.0)

    # Blink rate (decision 6)
    blink_window_s: float = 60.0

    # Pulse (decision 7)
    pulse_window_s: float = 10.0
    pulse_band_hz: tuple[float, float] = (0.6, 3.5)
    beat_min_s: float = 0.33  # 180 bpm
    beat_max_s: float = 1.5  # 40 bpm
    beat_off_median: float = 0.3
    rmssd_min_intervals: int = 5

    # Baseline (decision 8)
    baseline_window_s: float = 30 * 60.0
    baseline_min_n: int = 60
    mad_scale: float = 1.4826


PARAMS = Params()
