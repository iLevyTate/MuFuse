from __future__ import annotations

import numpy as np
import pytest

from mufuse.acquisition.timing import Retimer

RATE = 256.0
PERIOD = 1 / RATE
RNG = np.random.default_rng(1)


def _bursty_host_ts(n: int, t0: float = 1000.0, per_packet: int = 2) -> np.ndarray:
    """Arrival-time stamps like BrainFlow's: samples in one packet share a time, plus jitter."""
    true = t0 + np.arange(n) * PERIOD
    packet_time = true[per_packet - 1 :: per_packet].repeat(per_packet)[:n]
    return packet_time + RNG.uniform(0, 0.03, size=n).repeat(1)


def test_keeps_every_sample_and_is_strictly_increasing() -> None:
    host = _bursty_host_ts(2048)
    out = Retimer(RATE).retime(host)
    assert out.size == host.size
    assert np.all(np.diff(out) > 0)


def test_spacing_is_close_to_nominal_despite_jitter() -> None:
    out = Retimer(RATE).retime(_bursty_host_ts(5120))
    spacing = np.diff(out)
    assert np.median(spacing) == pytest.approx(PERIOD, rel=0.01)
    assert spacing.min() >= 0.5 * PERIOD


def test_tracks_host_clock_without_drifting_away() -> None:
    host = _bursty_host_ts(256 * 60)  # one minute
    out = Retimer(RATE).retime(host)
    assert abs(out[-1] - host[-1]) < 0.05


def test_tracks_a_device_running_slightly_fast() -> None:
    fast = 1000.0 + np.arange(256 * 60) / 256.5  # device clock 0.2% fast vs nominal
    out = Retimer(RATE).retime(fast)
    assert abs(out[-1] - fast[-1]) < 0.01


def test_real_gap_is_preserved() -> None:
    segments = [1000 + np.arange(256) * PERIOD, 1003 + np.arange(256) * PERIOD]
    host = np.concatenate(segments).astype(np.float64)
    out = Retimer(RATE).retime(host)
    assert np.max(np.diff(out)) > 1.9


def test_state_carries_across_calls() -> None:
    host = _bursty_host_ts(1024)
    whole = Retimer(RATE).retime(host)
    retimer = Retimer(RATE)
    parts = np.concatenate([retimer.retime(host[:300]), retimer.retime(host[300:])])
    np.testing.assert_allclose(parts, whole)


def test_empty_input() -> None:
    assert Retimer(RATE).retime(np.empty(0)).size == 0
