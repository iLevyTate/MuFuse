from __future__ import annotations

import numpy as np
import pytest

from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.simulated import SimulatedAthena
from mufuse.acquisition.types import Chunk, SourceError, StreamKind
from tests.conftest import FakeClock


def _collect(src: SimulatedAthena, clock: FakeClock, seconds: float) -> dict[StreamKind, Chunk]:
    clock.advance(seconds)
    return {c.kind: c for c in src.read()}


def test_streams_match_athena_layout(clock: FakeClock) -> None:
    src = SimulatedAthena(clock=clock)
    assert dict(src.streams) == dict(ATHENA_STREAMS)
    assert src.device.driver == "simulated"


def test_read_before_start_raises(clock: FakeClock) -> None:
    with pytest.raises(SourceError):
        SimulatedAthena(clock=clock).read()


@pytest.mark.parametrize(("kind", "rate"), [("eeg", 256), ("motion", 52), ("optics", 64)])
def test_sample_counts_follow_nominal_rates(clock: FakeClock, kind: str, rate: int) -> None:
    src = SimulatedAthena(clock=clock)
    src.start()
    chunk = _collect(src, clock, 2.0)[StreamKind(kind)]
    assert chunk.n_samples == 2 * rate
    assert chunk.data.shape[1] == len(ATHENA_STREAMS[StreamKind(kind)].channel_names)


def test_consecutive_reads_are_contiguous(clock: FakeClock) -> None:
    src = SimulatedAthena(clock=clock)
    src.start()
    first = _collect(src, clock, 0.5)[StreamKind.EEG]
    second = _collect(src, clock, 0.5)[StreamKind.EEG]
    gap = second.timestamps[0] - first.timestamps[-1]
    assert gap == pytest.approx(1 / 256)


def test_same_seed_is_deterministic(clock: FakeClock) -> None:
    a, b = SimulatedAthena(clock=clock, seed=7), SimulatedAthena(clock=FakeClock(), seed=7)
    a.start()
    b.start()
    clock.advance(1.0)
    b_clock = b._clock  # pyright: ignore[reportPrivateUsage]
    assert isinstance(b_clock, FakeClock)
    b_clock.advance(1.0)
    ea = next(c for c in a.read() if c.kind is StreamKind.EEG)
    eb = next(c for c in b.read() if c.kind is StreamKind.EEG)
    np.testing.assert_array_equal(ea.data, eb.data)


def test_eeg_has_alpha_peak(clock: FakeClock) -> None:
    src = SimulatedAthena(clock=clock)
    src.start()
    eeg = _collect(src, clock, 8.0)[StreamKind.EEG].data[:, 1]  # AF7
    freqs = np.fft.rfftfreq(eeg.size, 1 / 256)
    power = np.abs(np.fft.rfft(eeg - eeg.mean())) ** 2
    band = (freqs > 2) & (freqs < 40)
    assert 9.0 <= freqs[band][np.argmax(power[band])] <= 11.0


def test_dropout_window_produces_no_samples(clock: FakeClock) -> None:
    src = SimulatedAthena(clock=clock, dropouts=[(1.0, 2.0)])
    src.start()
    eeg = _collect(src, clock, 3.0)[StreamKind.EEG]
    rel = eeg.timestamps - clock.now + 3.0
    assert not np.any((rel >= 1.0) & (rel < 2.0))
    assert eeg.n_samples == 2 * 256


def test_stop_is_idempotent(clock: FakeClock) -> None:
    src = SimulatedAthena(clock=clock)
    src.start()
    src.stop()
    src.stop()
