from __future__ import annotations

import numpy as np
import pytest

from mufuse.acquisition.signal_check import FULL_SCALE_UV, RAIL_UV, classify_channel, spread_uv

RNG = np.random.default_rng(0)
T = np.arange(512) / 256


def test_flat_line() -> None:
    assert classify_channel(np.zeros(512) + 0.05 * RNG.standard_normal(512)) == "flat"


def test_plausible_eeg_with_alpha() -> None:
    eeg = 15 * np.sin(2 * np.pi * 10 * T) + 8 * RNG.standard_normal(512)
    assert classify_channel(eeg) == "ok"


def test_single_blink_is_still_ok() -> None:
    eeg = 15 * np.sin(2 * np.pi * 10 * T) + 8 * RNG.standard_normal(512)
    eeg[200:260] += 150 * np.hanning(60)  # ~150 µV blink on AF7
    assert classify_channel(eeg) == "ok"


def test_sustained_large_noise() -> None:
    assert classify_channel(120 * RNG.standard_normal(512)) == "noisy"


def test_railed() -> None:
    eeg = 8 * RNG.standard_normal(512)
    eeg[100:300] = 2000.0
    assert classify_channel(eeg) == "railed"


@pytest.mark.parametrize("bad", [np.full(512, np.nan), np.empty(0)])
def test_unusable_input_is_flat(bad: np.ndarray) -> None:
    assert classify_channel(bad) == "flat"


def test_spread_matches_standard_deviation_for_gaussian_noise() -> None:
    rng = np.random.default_rng(0)
    assert spread_uv(rng.normal(0, 20, 20_000)) == pytest.approx(20, rel=0.03)
    assert spread_uv(np.array([np.nan])) == 0.0


# The rail sits at the amplifier's full scale, ±725 µV since BrainFlow 5.23 ----------------------


def test_rail_threshold_is_within_2_percent_of_full_scale() -> None:
    assert pytest.approx(0.98 * FULL_SCALE_UV) == RAIL_UV
    assert FULL_SCALE_UV == 725.0


def test_a_channel_pinned_at_full_scale_is_railed() -> None:
    # Regression: with the old 1000 µV threshold no Athena sample could ever count as railed.
    eeg = 8 * RNG.standard_normal(512)
    eeg[100:200] = 725.0
    eeg[300:350] = -725.0
    assert classify_channel(eeg) == "railed"


def test_large_samples_short_of_the_rail_are_not_railed() -> None:
    eeg = 8 * RNG.standard_normal(512)
    eeg[100:300:4] = 650.0  # big, but more than 2% from full scale
    assert classify_channel(eeg) == "ok"


def test_a_few_samples_at_the_rail_do_not_rail_the_window() -> None:
    eeg = 8 * RNG.standard_normal(512)
    eeg[:40] = 725.0  # under 10% of the window
    assert classify_channel(eeg) == "ok"
