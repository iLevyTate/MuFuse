"""Feature frames from the simulated headband (003): what the gate checks in CI."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from mufuse.acquisition.simulated import Wearer
from mufuse.acquisition.types import Chunk, StreamKind
from mufuse.features.engine import FeatureEngine, FeatureFrame, extract
from mufuse.features.params import FEATURES_VERSION
from mufuse.quality.rules import RULES_VERSION
from mufuse.recording.reader import LoadedSession
from tests.conftest import QUICK, FakeClock, rehearse

RESTING = replace(QUICK, resting=True)


def _live(
    wearer: Wearer, seconds: float, seed: int = 0
) -> tuple[list[FeatureFrame], list[list[Chunk]]]:
    reads = rehearse(wearer, FakeClock(), seconds, seed=seed)
    engine = FeatureEngine()
    frames = [f for read in reads for f in engine.feed(read)]
    return frames + engine.finish(), reads


def _values(frames: list[FeatureFrame], name: str) -> np.ndarray:
    return np.array([f.values[name] for f in frames if f.values[name] is not None])


@pytest.mark.parametrize(("exponent", "bpm"), [(1.0, 55.0), (1.5, 72.0), (2.0, 100.0)])
def test_the_exponent_and_the_heart_rate_of_the_wearer_are_found(
    exponent: float, bpm: float
) -> None:
    frames, _ = _live(replace(RESTING, exponent=exponent, heart_bpm=bpm), 90.0)
    found = _values(frames, "exponent")
    assert found.size > 70
    assert np.median(found) == pytest.approx(exponent, abs=0.1)
    hr = _values(frames, "hr_bpm")
    assert hr.size > 70
    assert np.abs(hr - bpm).max() <= 3.0  # the ROADMAP gate, against the simulator's truth


def test_the_alpha_bursts_show_as_a_10_hz_peak() -> None:
    frames, _ = _live(RESTING, 60.0)
    assert np.median(_values(frames, "alpha_hz")) == pytest.approx(10.0, abs=0.5)


def test_every_frame_carries_the_versions_that_made_it() -> None:
    frames, _ = _live(RESTING, 10.0)
    assert frames
    assert {(f.features, f.rules) for f in frames} == {(FEATURES_VERSION, RULES_VERSION)}


def test_a_lifted_forehead_sensor_is_left_out_and_the_other_still_counts() -> None:
    frames, _ = _live(replace(RESTING, lifted=((0.0, 60.0, "AF7"),)), 40.0)
    assert _values(frames, "af7_exponent").size == 0
    assert _values(frames, "af8_exponent").size > 20
    assert _values(frames, "exponent").size > 20


def test_the_ears_are_never_read() -> None:
    plain, _ = _live(RESTING, 40.0)
    ears_off, _ = _live(replace(RESTING, lifted=((0.0, 60.0, "TP9"), (0.0, 60.0, "TP10"))), 40.0)
    assert [f.values["exponent"] for f in plain] == [f.values["exponent"] for f in ears_off]


def test_no_heart_rate_while_the_head_moves() -> None:
    frames, _ = _live(replace(RESTING, turns=((20.0, 40.0),)), 50.0)
    moving = [f for f in frames if 20.0 < f.t - frames[0].t + 1.0 < 40.0]
    assert moving
    assert all(f.values["hr_bpm"] is None for f in moving)


def test_blinks_are_counted_per_minute_once_a_minute_is_judged() -> None:
    every_4_s = tuple((float(t), t + 0.5) for t in range(5, 100, 4))  # one blink each
    frames, _ = _live(replace(RESTING, blinks=every_4_s), 100.0)
    rate = _values(frames, "blinks_per_min")
    assert rate.size > 0
    assert np.median(rate) == pytest.approx(15.0, abs=2.0)
    assert all(f.values["blinks_per_min"] is None for f in frames[:55])


def test_z_scores_start_once_the_baseline_holds_a_minute_of_values() -> None:
    frames, _ = _live(RESTING, 100.0)
    with_z = [f for f in frames if f.z["exponent"] is not None]
    assert with_z
    assert with_z[0].t - frames[0].t >= 59.0
    assert (
        abs(float(np.median([z for f in with_z if (z := f.z["exponent"]) is not None]))) < 2.0
    )  # a steady wearer


def _session(reads: list[list[Chunk]], tmp_path: Path) -> LoadedSession:
    streams: dict[StreamKind, tuple[np.ndarray, np.ndarray]] = {}
    for kind in StreamKind:
        parts = [c for read in reads for c in read if c.kind is kind]
        streams[kind] = (
            np.concatenate([c.timestamps for c in parts]),
            np.vstack([c.data for c in parts]),
        )
    return LoadedSession(path=tmp_path, manifest={}, streams=streams, markers=[], gaps=[])


def test_live_frames_equal_the_recording_replayed(tmp_path: Path) -> None:
    live, reads = _live(replace(RESTING, blinks=((30.0, 40.0),), turns=((50.0, 55.0),)), 80.0)
    replayed = extract(_session(reads, tmp_path))
    assert replayed == live
