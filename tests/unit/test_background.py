from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.simulated import SimulatedAthena
from mufuse.acquisition.supervisor import State, StreamSupervisor
from mufuse.acquisition.types import StreamKind
from mufuse.hwtest.background import BackgroundAcquisition
from mufuse.recording.format import Marker
from mufuse.recording.reader import load_session
from mufuse.recording.writer import SessionWriter


def _wait_until(condition: Callable[[], bool], timeout: float = 3.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met in time")


def test_collects_samples_in_the_background() -> None:
    acq = BackgroundAcquisition(StreamSupervisor(SimulatedAthena), poll_s=0.01)
    with acq:
        _wait_until(lambda: acq.counts()[StreamKind.EEG] > 50)
        assert acq.state is State.STREAMING
        latest = acq.latest(StreamKind.OPTICS)
        assert latest is not None
        assert latest.shape == (len(ATHENA_STREAMS[StreamKind.OPTICS].channel_names),)
        ts, data = acq.eeg_between(0.0, time.time() + 1)
        assert ts.size == data.shape[0] > 0
    assert acq.state is State.STOPPED


def test_records_pauses_in_data() -> None:
    acq = BackgroundAcquisition(
        StreamSupervisor(lambda: SimulatedAthena(dropouts=[(0.2, 0.6)])),
        poll_s=0.01,
        pause_threshold_s=0.15,
    )
    with acq:
        _wait_until(lambda: bool(acq.pauses()))
    (pause,) = acq.pauses()
    assert 0.3 < pause.duration < 0.55


def test_seconds_since_data() -> None:
    acq = BackgroundAcquisition(StreamSupervisor(SimulatedAthena), poll_s=0.01)
    assert acq.seconds_since_data() is None
    with acq:
        _wait_until(lambda: acq.seconds_since_data() is not None)
        seconds = acq.seconds_since_data()
        assert seconds is not None
        assert seconds < 0.5


def test_writes_session_with_markers_and_finalizes(tmp_path: Path) -> None:
    acq = BackgroundAcquisition(
        StreamSupervisor(SimulatedAthena),
        writer_factory=lambda src: SessionWriter.create(tmp_path, src.device, src.streams),
        poll_s=0.01,
    )
    with acq:
        _wait_until(lambda: acq.counts()[StreamKind.EEG] > 50)
        acq.add_marker(Marker(t=time.time(), kind="moment", label="moment", source="keyboard"))
        _wait_until(lambda: acq.counts()[StreamKind.EEG] > 100)
    assert acq.session_dir is not None
    session = load_session(acq.session_dir)
    assert session.finalized
    assert len(session.markers) == 1
    assert session.streams[StreamKind.EEG][0].size == acq.counts()[StreamKind.EEG]


def test_stop_is_idempotent() -> None:
    acq = BackgroundAcquisition(StreamSupervisor(SimulatedAthena), poll_s=0.01)
    acq.start()
    acq.stop()
    acq.stop()
    assert acq.error is None
