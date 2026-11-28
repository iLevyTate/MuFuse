"""The fNIRS pipeline on simulated sessions (004 decisions 1-5, 8)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from mufuse.acquisition.optics import OPTICS_FULL_SCALE
from mufuse.acquisition.simulated import Wearer, hemo_envelope
from mufuse.acquisition.types import Chunk, StreamKind
from mufuse.fnirs.mbll import DETECTORS, FNIRS_VERSION
from mufuse.fnirs.pipeline import NotAvailableError, analyze
from mufuse.recording.reader import LoadedSession
from tests.conftest import QUICK, FakeClock, rehearse


def _session(wearer: Wearer, seconds: float, tmp_path: Path, seed: int = 0) -> LoadedSession:
    reads = rehearse(wearer, FakeClock(), seconds, seed=seed)
    streams: dict[StreamKind, tuple[np.ndarray, np.ndarray]] = {}
    for kind in StreamKind:
        parts: list[Chunk] = [c for read in reads for c in read if c.kind is kind]
        streams[kind] = (
            np.concatenate([c.timestamps for c in parts]),
            np.vstack([c.data for c in parts]),
        )
    return LoadedSession(path=tmp_path, manifest={}, streams=streams, markers=[], gaps=[])


def test_the_envelope_rises_and_falls_smoothly() -> None:
    t = np.arange(0.0, 40.0, 0.5)
    env = hemo_envelope(t, ((10.0, 30.0, 2.0),))
    assert env[t < 10.0].max() == 0.0
    assert env[(t >= 15.0) & (t <= 25.0)] == pytest.approx(2.0)
    assert env[t == 12.5][0] == pytest.approx(1.0)  # half way up the 5 s ramp


def test_a_planted_response_is_found_at_every_detector(tmp_path: Path) -> None:
    wearer = replace(QUICK, hemo=((60.0, 100.0, 1.0),))
    hemo = analyze(_session(wearer, 160.0, tmp_path))
    during = (hemo.t - hemo.t[0] > 70.0) & (hemo.t - hemo.t[0] < 90.0)
    before = (hemo.t - hemo.t[0] > 35.0) & (hemo.t - hemo.t[0] < 55.0)
    for k, detector in enumerate(DETECTORS):
        rise = np.nanmean(hemo.hbo[during, k]) - np.nanmean(hemo.hbo[before, k])
        fall = np.nanmean(hemo.hbr[during, k]) - np.nanmean(hemo.hbr[before, k])
        assert rise > 0.5, detector  # 1 µM planted; the band-pass takes some of it
        assert fall < 0.0, detector


def test_no_response_reads_near_zero(tmp_path: Path) -> None:
    hemo = analyze(_session(QUICK, 120.0, tmp_path))
    assert np.nanmax(np.abs(hemo.outer_hbo()[hemo.t - hemo.t[0] > 30.0])) < 0.3


def test_seconds_of_movement_and_glare_are_left_out_and_counted(tmp_path: Path) -> None:
    session = _session(replace(QUICK, turns=((40.0, 50.0),)), 120.0, tmp_path)
    t, data = session.streams[StreamKind.OPTICS]
    rel = t - t[0]
    data = data.copy()
    data[(rel >= 70.0) & (rel < 75.0), 4:8] = OPTICS_FULL_SCALE  # a lamp on the sensors
    hemo = analyze(replace(session, streams={**session.streams, StreamKind.OPTICS: (t, data)}))
    assert hemo.moving > 0
    assert hemo.glare == int(((rel >= 70.0) & (rel < 75.0)).sum())
    assert np.isnan(hemo.hbo[(rel > 42.0) & (rel < 48.0)]).all()
    assert np.isnan(hemo.hbo[(rel > 71.0) & (rel < 74.0)]).all()
    assert 0.8 < hemo.used_share < 1.0


def test_each_output_carries_the_version_and_a_quality_index(tmp_path: Path) -> None:
    wearer = replace(QUICK, hemo=((40.0, 80.0, 1.0),))
    hemo = analyze(_session(wearer, 100.0, tmp_path))
    assert hemo.version == FNIRS_VERSION
    assert set(hemo.sqi) == set(DETECTORS)
    assert any(v is not None and v > 0 for v in hemo.sqi.values())  # HbO and HbR move apart


def test_short_channel_regression_takes_the_shared_part_out(tmp_path: Path) -> None:
    wearer = replace(QUICK, hemo=((60.0, 100.0, 1.0),))
    session = _session(wearer, 160.0, tmp_path)
    plain, regressed = analyze(session), analyze(session, short_channel=True)
    assert regressed.short_channel
    lo = DETECTORS.index("LO")
    # The simulator puts the same response under inner and outer: regression removes most of it.
    assert np.nanstd(regressed.hbo[:, lo]) < 0.5 * np.nanstd(plain.hbo[:, lo])


def test_without_16_channel_optics_it_is_not_available(tmp_path: Path) -> None:
    session = _session(QUICK, 30.0, tmp_path)
    t, data = session.streams[StreamKind.OPTICS]
    eight = replace(session, streams={**session.streams, StreamKind.OPTICS: (t, data[:, :9])})
    with pytest.raises(NotAvailableError, match="16-channel"):
        analyze(eight)
    with pytest.raises(NotAvailableError, match="no optics"):
        analyze(replace(session, streams={StreamKind.EEG: session.streams[StreamKind.EEG]}))
