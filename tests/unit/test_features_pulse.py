"""Heart rate and pulse-based variability from the forehead optics (003 decision 7)."""

from __future__ import annotations

import numpy as np
import pytest

from mufuse.features.pulse import beat_times, has_pulse, heart, rmssd_ms

FS = 64.0


def _pulse(intervals: list[float], noise: float = 0.0, seed: int = 0) -> np.ndarray:
    """A pulse wave whose beats fall after the given intervals (s), sampled at 64 Hz."""
    beats = np.cumsum([0.4, *intervals])
    t = np.arange(0, beats[-1] + 0.6, 1 / FS)
    wave = np.zeros_like(t)
    for b in beats:  # a narrow bump per beat, like the systolic upstroke
        wave += np.exp(-0.5 * ((t - b) / 0.08) ** 2)
    rng = np.random.default_rng(seed)
    return 20_000.0 + 150.0 * wave + noise * rng.standard_normal(t.size) + 2.0 * t


@pytest.mark.parametrize("bpm", [50.0, 72.0, 95.0, 130.0])
def test_a_steady_heart_rate_is_read_within_one_bpm(bpm: float) -> None:
    found = heart(_pulse([60 / bpm] * 12, noise=5.0), FS)
    assert found is not None
    assert found.bpm == pytest.approx(bpm, abs=1.0)


def test_beats_are_timed_between_samples() -> None:
    intervals = [0.81, 0.79, 0.83, 0.77, 0.80, 0.82, 0.78, 0.84]
    found = beat_times(_pulse(intervals), FS)
    assert np.diff(found) == pytest.approx(intervals, abs=0.004)  # a sample is 15.6 ms


def test_rmssd_of_a_known_beat_train() -> None:
    intervals = [0.80, 0.85, 0.80, 0.85, 0.80, 0.85, 0.80, 0.85]  # every difference 50 ms
    found = heart(_pulse(intervals), FS)
    assert found is not None
    assert found.rmssd_ms == pytest.approx(50.0, abs=5.0)


def test_an_odd_interval_is_left_out_of_the_variability() -> None:
    assert rmssd_ms(np.array([0.8, 0.8, 0.8, 0.8, 0.8, 0.8])) == pytest.approx(0.0)
    with_miss = np.array([0.8, 0.8, 1.6, 0.8, 0.8, 0.8, 0.8])  # a missed beat doubles one
    assert rmssd_ms(with_miss) == pytest.approx(0.0)


def test_too_few_intervals_give_no_variability() -> None:
    assert rmssd_ms(np.array([0.8, 0.81, 0.8])) is None


def test_noise_is_not_a_pulse_and_a_heartbeat_is() -> None:
    flat = 20_000.0 + np.random.default_rng(1).standard_normal(640)
    assert not has_pulse(flat, FS)
    t = np.arange(640) / FS
    assert has_pulse(20_000.0 + 40.0 * np.sin(2 * np.pi * 1.2 * t) + flat - 20_000.0, FS)
