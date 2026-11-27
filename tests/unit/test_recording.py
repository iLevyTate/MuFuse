from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.types import Chunk, DeviceInfo, StreamKind
from mufuse.recording.format import FORMAT_VERSION, Gap, Marker, ReconnectStep, new_session_id
from mufuse.recording.reader import load_session
from mufuse.recording.writer import SessionWriter
from tests.conftest import FakeClock

DEVICE = DeviceInfo(name="MuseS-TEST", preset="p1041", driver="simulated")


def _eeg(t0: float, n: int) -> Chunk:
    ts = t0 + np.arange(n) / 256
    return Chunk(StreamKind.EEG, ts, np.tile(np.arange(n, dtype=float)[:, None], (1, 8)))


@pytest.fixture
def writer(tmp_path: Path, clock: FakeClock) -> SessionWriter:
    return SessionWriter.create(tmp_path, DEVICE, ATHENA_STREAMS, notes="unit", clock=clock)


def test_session_id_format() -> None:
    sid = new_session_id(1_700_000_000.0)
    assert sid.startswith("20231114T221320Z-")
    assert len(sid.split("-")[1]) == 4


def test_manifest_written_at_start(writer: SessionWriter) -> None:
    manifest = json.loads((writer.session_dir / "manifest.json").read_text())
    assert manifest["format_version"] == FORMAT_VERSION
    assert manifest["ended_at"] is None
    assert manifest["device"]["name"] == "MuseS-TEST"
    assert manifest["streams"]["eeg"]["columns"][:5] == ["t", "TP9", "AF7", "AF8", "TP10"]


def test_round_trip(writer: SessionWriter, clock: FakeClock) -> None:
    writer.write([_eeg(clock.now, 256)])
    writer.write([_eeg(clock.now + 1.0, 256)])
    writer.add_marker(Marker(t=clock.now + 0.5, kind="moment", label="hi", source="keyboard"))
    clock.advance(2.0)
    writer.finalize()

    session = load_session(writer.session_dir)
    ts, data = session.streams[StreamKind.EEG]
    assert ts.shape == (512,)
    assert data.shape == (512, 8)
    assert session.finalized
    assert session.markers[0].label == "hi"
    assert session.manifest["completeness"]["eeg"] == {"expected": 512, "received": 512}


def test_completeness_counts_missing_samples(writer: SessionWriter, clock: FakeClock) -> None:
    writer.write([_eeg(clock.now, 256)])
    writer.write([_eeg(clock.now + 2.0, 256)])  # one second (256 samples) missing
    writer.finalize()
    assert load_session(writer.session_dir).manifest["completeness"]["eeg"] == {
        "expected": 768,
        "received": 512,
    }


def test_gaps_persist(writer: SessionWriter, clock: FakeClock) -> None:
    writer.add_gap(Gap(stream="eeg", start=clock.now, end=clock.now + 3, reason="stall"))
    writer.finalize()
    gap = load_session(writer.session_dir).gaps[0]
    assert gap.reason == "stall"
    assert gap.end == pytest.approx(gap.start + 3)


def test_reconnect_steps_persist(writer: SessionWriter, clock: FakeClock) -> None:
    steps = [
        ReconnectStep(clock.now, "lost", "stall"),
        ReconnectStep(clock.now + 1.0, "attempt"),
        ReconnectStep(clock.now + 17.0, "failed", "no device"),
    ]
    for step in steps:
        writer.add_reconnect_step(step)
    writer.close_files()  # as after a crash: every step was flushed when it happened
    assert load_session(writer.session_dir).reconnects == steps


def test_session_from_before_reconnect_steps_has_none(writer: SessionWriter) -> None:
    writer.finalize()
    (writer.session_dir / "reconnects.jsonl").unlink()
    assert load_session(writer.session_dir).reconnects == []


def test_unfinalized_session_with_partial_row_is_readable(writer: SessionWriter) -> None:
    writer.write([_eeg(0.0, 10)])
    writer.close_files()  # simulate a crash: no finalize
    with (writer.session_dir / "eeg.f64").open("ab") as fh:
        fh.write(b"\x00" * 13)  # torn trailing row
    session = load_session(writer.session_dir)
    assert not session.finalized
    assert session.streams[StreamKind.EEG][0].shape == (10,)


def test_finalize_is_idempotent(writer: SessionWriter) -> None:
    writer.finalize()
    writer.finalize()


def test_lost_subpackets_are_stored_next_to_completeness(
    writer: SessionWriter, clock: FakeClock
) -> None:
    writer.write([_eeg(clock.now, 256)])
    writer.finalize(lost_subpackets={StreamKind.EEG: 3, StreamKind.MOTION: 0, StreamKind.OPTICS: 1})
    manifest = load_session(writer.session_dir).manifest
    assert manifest["lost_subpackets"] == {"eeg": 3, "motion": 0, "optics": 1}
    assert manifest["completeness"]["eeg"] == {"expected": 256, "received": 256}


def test_sessions_without_lost_subpackets_still_load(writer: SessionWriter) -> None:
    writer.finalize()  # as written before the field existed
    session = load_session(writer.session_dir)
    assert session.finalized
    assert "lost_subpackets" not in session.manifest
