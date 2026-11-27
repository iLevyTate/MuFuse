"""Movement from the motion sensors, once per stretch (contracts/quality-rules.md, section 6)."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from mufuse.acquisition.types import FloatArray, StreamKind
from mufuse.quality.engine import QualityEngine
from mufuse.quality.motion import movement
from mufuse.quality.rules import RULES
from tests.conftest import QUICK, FakeClock, eeg_chunk, motion_chunk, rehearse

HZ = 52
RNG = np.random.default_rng(5)


def _still(n: int = HZ) -> FloatArray:
    """A head at rest: gravity on ACC_Z and a little sensor noise on all six columns."""
    data = 0.002 * RNG.standard_normal((n, 6))
    data[:, 2] += 1.0
    return data


def _alternating(size: float, n: int = HZ) -> FloatArray:
    return size * np.where(np.arange(n) % 2 == 0, 1.0, -1.0)


def test_too_few_samples_is_unknown() -> None:
    assert RULES.motion_min_n == 26
    assert movement(_still(25)) == "unknown"
    assert movement(np.empty((0, 6))) == "unknown"
    assert movement(_still(26)) == "still"


def test_a_still_head_is_still() -> None:
    assert movement(_still()) == "still"


@pytest.mark.parametrize(("each_axis_dps", "expected"), [(12.0, "moving"), (11.0, "still")])
def test_the_gyroscope_limit_is_on_all_three_axes_together(
    each_axis_dps: float, expected: str
) -> None:
    data = _still()
    data[:, 3:6] = each_axis_dps  # rms over three axes: 20.8 and 19.1 deg/s
    assert movement(data) == expected


@pytest.mark.parametrize("axis", [0, 1, 2])
def test_the_accelerometer_limit_on_each_axis(axis: int) -> None:
    shaken, nudged = _still(), _still()
    shaken[:, axis] += _alternating(0.06)
    nudged[:, axis] += _alternating(0.04)
    assert movement(shaken) == "moving"
    assert movement(nudged) == "still"


def test_a_sample_at_the_stretch_end_belongs_to_the_next_stretch() -> None:
    eeg = 10.0 * RNG.standard_normal((3 * 256, 4))
    motion = _still(3 * HZ)
    motion[HZ, 3] = 1000.0  # stamped 101.0: the end of the first stretch, the start of the second
    engine = QualityEngine()
    chunks = [eeg_chunk(eeg, 100.0), motion_chunk(motion, 100.0)]
    answers = engine.feed(chunks).answers + engine.finish().answers
    assert [a.movement for a in answers] == ["still", "moving", "still"]


def test_a_simulated_head_turn_is_moving(clock: FakeClock) -> None:
    reads = rehearse(replace(QUICK, turns=((3.0, 5.0),)), clock, 8.0)
    chunks = [c for read in reads for c in read if c.kind is StreamKind.MOTION]
    data = np.vstack([c.data for c in chunks])
    t = np.concatenate([c.timestamps for c in chunks])
    t -= t[0]

    def second(start: float) -> FloatArray:
        return data[(t >= start) & (t < start + 1.0)]

    assert [movement(second(s)) for s in (1.0, 2.0, 3.0, 4.0, 6.0)] == [
        "still",
        "still",
        "moving",
        "moving",
        "still",
    ]
