from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mufuse.acquisition.types import Chunk, StreamKind
from mufuse.runlog import ConnectRun, TimeToSignal, append_run, log_path, read_runs, summarize
from tests.conftest import FakeClock


def _chunk(kind: StreamKind, n: int = 4) -> Chunk:
    return Chunk(kind, np.arange(n, dtype=np.float64), np.zeros((n, 1)))


def _run(
    outcome: str = "signal", seconds: float | None = 5.0, label: str = "H3 r1 1/10"
) -> ConnectRun:
    return ConnectRun(
        at="2026-11-26T09:20:30",
        command="stream",
        source="athena",
        device="MuseS-C27F",
        preset="p1041",
        outcome=outcome,
        seconds_to_signal=seconds,
        elapsed_s=seconds or 12.0,
        error=None if outcome == "signal" else "BOARD_NOT_READY_ERROR:7",
        label=label,
    )


def test_time_to_signal_reports_once_on_first_eeg(clock: FakeClock) -> None:
    timer = TimeToSignal(t0=clock.now)
    clock.advance(3.0)
    assert timer.observe([_chunk(StreamKind.MOTION)], clock.now) is None
    clock.advance(1.25)
    assert timer.observe([_chunk(StreamKind.EEG)], clock.now) == pytest.approx(4.25)
    assert timer.seconds == pytest.approx(4.25)
    clock.advance(1.0)
    assert timer.observe([_chunk(StreamKind.EEG)], clock.now) is None
    assert timer.seconds == pytest.approx(4.25)


def test_time_to_signal_ignores_empty_eeg_chunks(clock: FakeClock) -> None:
    timer = TimeToSignal(t0=clock.now)
    clock.advance(2.0)
    assert timer.observe([_chunk(StreamKind.EEG, n=0)], clock.now) is None
    assert timer.seconds is None


def test_append_then_read_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "logs" / "connect.jsonl"
    first, second = _run(), _run("connect_error", None, "H3 r1 2/10")
    append_run(first, path)
    append_run(second, path)
    assert read_runs(path) == [first, second]


def test_read_skips_a_torn_last_line_and_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "connect.jsonl"
    assert read_runs(path) == []
    append_run(_run(), path)
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"at": "2026-11-26T09:2')  # crash mid-write
    assert read_runs(path) == [_run()]


def test_log_path_honours_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUFUSE_LOG_DIR", str(tmp_path))
    assert log_path() == tmp_path / "connect.jsonl"


def test_summarize_counts_fast_signals_against_the_bar() -> None:
    runs = [_run(seconds=s) for s in (4.0, 6.5, 15.0, 14.9, 5.0, 7.0, 8.0, 9.0, 3.0)]
    runs.append(_run("connect_error", None))
    summary = summarize(runs, threshold_s=15.0, need=9)
    assert (summary.passed, summary.attempts, summary.ok) == (9, 10, True)


def test_summarize_fails_slow_or_signalless_runs() -> None:
    runs = [_run(seconds=s) for s in (4.0, 16.0, 5.0)] + [_run("no_signal", None)]
    summary = summarize(runs, threshold_s=15.0, need=3)
    assert (summary.passed, summary.attempts, summary.ok) == (2, 4, False)
