from __future__ import annotations

from pathlib import Path

import numpy as np

from mufuse.acquisition.playback import PlaybackSource
from mufuse.acquisition.simulated import SimulatedAthena
from mufuse.acquisition.supervisor import StreamSupervisor
from mufuse.acquisition.types import StreamKind
from mufuse.config import UserConfig, load_config, save_config
from mufuse.recording.format import Marker
from mufuse.recording.reader import load_session
from mufuse.recording.writer import SessionWriter
from tests.conftest import FakeClock


def _record(tmp_path: Path, clock: FakeClock, seconds: float, **sim_kwargs: object) -> Path:
    sim = SimulatedAthena(clock=clock, **sim_kwargs)  # type: ignore[arg-type]
    sup = StreamSupervisor(lambda: sim, clock=clock)
    sup.start()
    writer = SessionWriter.create(tmp_path, sim.device, sim.streams, notes="it", clock=clock)
    sup.on_gap_closed = writer.add_gap
    for i in range(round(seconds / 0.05)):
        clock.advance(0.05)
        writer.write(sup.poll())
        if i == 20:
            writer.add_marker(Marker(t=clock.now, kind="moment", label="m", source="keyboard"))
    sup.stop()
    writer.finalize()
    return writer.session_dir


def test_simulated_record_reload_with_marker_alignment(tmp_path: Path, clock: FakeClock) -> None:
    session = load_session(_record(tmp_path, clock, 5.0))
    ts, _ = session.streams[StreamKind.EEG]
    assert ts.size == 5 * 256
    marker_t = session.markers[0].t
    nearest = ts[np.argmin(np.abs(ts - marker_t))]
    assert abs(nearest - marker_t) <= 1 / 256  # SC-004: within ±1 sample
    for kind in StreamKind:
        c = session.manifest["completeness"][kind.value]
        assert c["received"] == c["expected"]


def test_dropout_is_recorded_as_gap_not_interpolated(tmp_path: Path, clock: FakeClock) -> None:
    session = load_session(_record(tmp_path, clock, 12.0, dropouts=[(2.0, 6.0)]))
    (gap,) = session.gaps
    assert gap.end is not None
    assert 3.5 <= gap.end - gap.start <= 4.5  # SC-003: ±0.5 s
    ts, _ = session.streams[StreamKind.EEG]
    assert np.max(np.diff(ts)) > 3.5  # hole preserved, not filled


def test_playback_reproduces_session(tmp_path: Path, clock: FakeClock) -> None:
    path = _record(tmp_path, clock, 2.0)
    original = load_session(path)
    play = PlaybackSource(path, realtime=False)
    play.start()
    chunks = {c.kind: c for c in play.read()}
    assert play.exhausted
    for kind, (ts, data) in original.streams.items():
        np.testing.assert_array_equal(chunks[kind].timestamps, ts)
        np.testing.assert_array_equal(chunks[kind].data, data)


def test_config_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "cfg.json"
    assert load_config(path) == UserConfig()
    save_config(UserConfig("MuseS-1234", "AA:BB"), path)
    assert load_config(path).last_device_name == "MuseS-1234"
    path.write_text("{not json")
    assert load_config(path) == UserConfig()
