"""The forehead spectrum: aperiodic exponent, alpha peak and band shares (003 decisions 2-5)."""

from __future__ import annotations

import numpy as np
import pytest

from mufuse.features.spectrum import (
    AperiodicFit,
    alpha_peak,
    band_shares,
    fit_aperiodic,
    pair_spectrum,
)

FS = 256.0


def _power_law(exponent: float, alpha_gain: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    freqs = np.arange(0.0, 128.5, 0.5)
    psd = np.zeros_like(freqs)
    psd[1:] = 100.0 * freqs[1:] ** -exponent
    psd *= 1 + (alpha_gain - 1) * np.exp(-0.5 * ((freqs - 10.0) / 0.7) ** 2)
    return freqs, psd


@pytest.mark.parametrize("exponent", [0.8, 1.5, 2.2])
def test_the_exponent_of_a_clean_power_law_is_recovered(exponent: float) -> None:
    fit = fit_aperiodic(*_power_law(exponent))
    assert fit is not None
    assert fit.exponent == pytest.approx(exponent, abs=1e-6)
    assert fit.r2 == pytest.approx(1.0)


def test_an_alpha_peak_does_not_bend_the_line() -> None:
    fit = fit_aperiodic(*_power_law(1.5, alpha_gain=6.0))
    assert fit is not None
    assert fit.exponent == pytest.approx(1.5, abs=1e-3)


def test_the_alpha_peak_is_found_where_it_stands_above_the_line() -> None:
    freqs, psd = _power_law(1.5, alpha_gain=4.0)
    fit = fit_aperiodic(freqs, psd)
    assert fit is not None
    peak = alpha_peak(freqs, psd, fit)
    assert peak is not None
    assert peak.hz == pytest.approx(10.0)
    assert peak.height == pytest.approx(np.log10(4.0), abs=1e-3)


def test_no_peak_is_a_normal_answer() -> None:
    freqs, psd = _power_law(1.5, alpha_gain=1.1)  # under the 0.1 log10 limit
    fit = fit_aperiodic(freqs, psd)
    assert fit is not None
    assert alpha_peak(freqs, psd, fit) is None


def test_a_flat_or_empty_spectrum_has_no_fit() -> None:
    freqs = np.arange(0.0, 128.5, 0.5)
    assert fit_aperiodic(freqs, np.zeros_like(freqs)) is None


def test_band_shares_add_to_the_part_of_2_to_40_hz_they_cover() -> None:
    freqs = np.arange(0.0, 128.5, 0.5)
    psd = np.where((freqs >= 2) & (freqs <= 40), 1.0, 0.0)
    shares = band_shares(freqs, psd)
    assert shares.theta == pytest.approx(8 / 77, abs=1e-9)  # 4-8 Hz: 8 bins of 77 in 2-40 Hz
    assert shares.alpha == pytest.approx(10 / 77, abs=1e-9)  # 8-13 Hz
    assert shares.beta == pytest.approx(34 / 77, abs=1e-9)  # 13-30 Hz


def test_the_pair_spectrum_of_a_10_hz_sine_peaks_at_10_hz() -> None:
    t = np.arange(512) / FS
    freqs, psd = pair_spectrum(20.0 * np.sin(2 * np.pi * 10.0 * t), FS)
    assert freqs[1] - freqs[0] == pytest.approx(0.5)
    assert freqs[int(np.argmax(psd))] == pytest.approx(10.0)


def test_white_noise_has_an_exponent_near_zero() -> None:
    rng = np.random.default_rng(0)
    spectra = [pair_spectrum(rng.standard_normal(512), FS)[1] for _ in range(40)]
    freqs = pair_spectrum(np.zeros(512), FS)[0]
    fit = fit_aperiodic(freqs, np.mean(spectra, axis=0))
    assert isinstance(fit, AperiodicFit)
    assert abs(fit.exponent) < 0.15
