from __future__ import annotations

import numpy as np
import pytest

from mufuse.acquisition.signal_check import classify_channel

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
