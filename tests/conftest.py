from __future__ import annotations

import numpy as np
import pytest

from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.simulated import Rehearsal, Wearer
from mufuse.acquisition.types import Chunk, StreamKind


class FakeClock:
    """Manually advanced clock so time-dependent code is deterministic in tests."""

    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self._start = start
        self._offset = 0.0  # kept separately so repeated small steps don't compound rounding

    @property
    def now(self) -> float:
        return self._start + self._offset

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self._offset += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture(autouse=True)
def _isolated_run_log(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    """Keep the CLI's connection log out of the real user log folder."""
    monkeypatch.setenv("MUFUSE_LOG_DIR", str(tmp_path_factory.mktemp("logs")))
    monkeypatch.delenv("MUFUSE_T0", raising=False)
    monkeypatch.delenv("MUFUSE_RUN_LABEL", raising=False)
    monkeypatch.delenv("MUFUSE_SIM_WEARER", raising=False)


# Signal quality helpers ------------------------------------------------------------------------

QUICK = Wearer(connect_s=0.0, first_data_s=0.0, scan_s=0.0, stop_s=0.0)  # data from second 0


def stream_chunk(kind: StreamKind, data: object, t0: float = 0.0) -> Chunk:
    """One chunk of `kind` from rows of samples, stamped at the stream's rate from `t0`."""
    rows = np.atleast_2d(np.asarray(data, dtype=np.float64))
    spec = ATHENA_STREAMS[kind]
    full = np.zeros((rows.shape[0], len(spec.channel_names)))
    full[:, : rows.shape[1]] = rows
    return Chunk(kind, t0 + np.arange(rows.shape[0]) / spec.sampling_rate, full)


def eeg_chunk(data: object, t0: float = 0.0) -> Chunk:
    """EEG from (n, 4) columns TP9, AF7, AF8, TP10; the AUX columns are zero."""
    return stream_chunk(StreamKind.EEG, data, t0)


def motion_chunk(data: object, t0: float = 0.0) -> Chunk:
    """MOTION from (n, 6) columns ACC_X/Y/Z, GYRO_X/Y/Z."""
    return stream_chunk(StreamKind.MOTION, data, t0)


def rehearse(
    wearer: Wearer, clock: FakeClock, seconds: float, *, tick: float = 0.25, seed: int = 0
) -> list[list[Chunk]]:
    """What a scripted wearer's headband delivers in `seconds`, one list of chunks per read."""
    source = Rehearsal(wearer, clock=clock, sleep=clock.advance, seed=seed).source()
    source.start()
    reads: list[list[Chunk]] = []
    for _ in range(round(seconds / tick)):
        clock.advance(tick)
        reads.append(source.read())
    return reads
