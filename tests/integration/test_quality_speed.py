"""How fast a session is judged (SC-007; the cost in contracts/quality-interface.md)."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.types import Chunk, DeviceInfo, StreamKind
from mufuse.quality.engine import QualityEngine, judge
from mufuse.quality.summary import summarize
from mufuse.recording.reader import load_session
from mufuse.recording.writer import SessionWriter
from tests.conftest import FakeClock

EEG_HZ, MOTION_HZ = 256, 52
T0 = 1_700_000_000.0


def _minute(rng: np.random.Generator, minute: int) -> list[Chunk]:
    t0 = T0 + 60 * minute
    n, m = 60 * EEG_HZ, 60 * MOTION_HZ
    t = np.arange(n) / EEG_HZ
    eeg = np.zeros((n, 8))
    eeg[:, :4] = 20.0 * np.sin(2 * np.pi * 10 * t)[:, None] + 8.0 * rng.standard_normal((n, 4))
    motion = 0.01 * rng.standard_normal((m, 6))
    motion[:, 2] += 1.0
    return [
        Chunk(StreamKind.EEG, t0 + t, eeg),
        Chunk(StreamKind.MOTION, t0 + np.arange(m) / MOTION_HZ, motion),
    ]


@pytest.fixture(scope="module")
def hour(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A 60-minute session: EEG and motion, written as the recorder writes them."""
    root = tmp_path_factory.mktemp("hour")
    writer = SessionWriter.create(
        root,
        DeviceInfo("SimulatedAthena", "p1041", "simulated"),
        ATHENA_STREAMS,
        clock=FakeClock(T0),
    )
    rng = np.random.default_rng(1)
    for minute in range(60):
        writer.write(_minute(rng, minute))
    writer.finalize()
    return writer.session_dir


def _fastest(run: Callable[[], object], limit_s: float, tries: int = 3) -> float:
    """The shortest of up to `tries` runs, stopping at the first one under the limit.

    A busy machine only ever makes a run slower, so the fastest run is the fair measure of
    the code and one slow run is not a failure.
    """
    best = float("inf")
    for _ in range(tries):
        started = time.perf_counter()
        run()
        best = min(best, time.perf_counter() - started)
        if best < limit_s:
            break
    return best


def test_an_hour_is_loaded_judged_and_summarized_in_under_30_s(hour: Path) -> None:
    judged: list[float] = []
    took = _fastest(lambda: judged.append(summarize(judge(load_session(hour))).judged_s), 30.0)
    assert judged[-1] == pytest.approx(3600.0, abs=1.0)
    assert took < 30.0, f"{took:.1f} s"


def test_judging_costs_under_5_ms_per_second_of_signal() -> None:
    rng = np.random.default_rng(2)
    chunks = [c for minute in range(2) for c in _minute(rng, minute)]

    def two_minutes() -> None:
        engine = QualityEngine()
        for eeg, motion in zip(chunks[::2], chunks[1::2], strict=True):
            for read in range(60 * 4):  # as the headband delivers it: a quarter second at a time
                e, m = slice(64 * read, 64 * (read + 1)), slice(13 * read, 13 * (read + 1))
                engine.feed(
                    [
                        Chunk(StreamKind.EEG, eeg.timestamps[e], eeg.data[e]),
                        Chunk(StreamKind.MOTION, motion.timestamps[m], motion.data[m]),
                    ]
                )
        engine.finish()

    took = _fastest(two_minutes, 0.005 * 120.0)
    assert took / 120.0 < 0.005, f"{1000 * took / 120:.2f} ms per second"
