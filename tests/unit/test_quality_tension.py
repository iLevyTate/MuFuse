"""Muscle activity in the forehead signal, per stretch (contracts/quality-rules.md, section 5)."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from mufuse.acquisition.types import Chunk, FloatArray, StreamKind
from mufuse.quality.answer import QualityAnswer
from mufuse.quality.engine import QualityEngine
from mufuse.quality.rules import RULES
from mufuse.quality.tension import tension, tension_level
from tests.conftest import QUICK, FakeClock, eeg_chunk, motion_chunk, rehearse

FS = 256
T = np.arange(FS) / FS
RNG = np.random.default_rng(9)


def _sine(hz: float, peak: float) -> FloatArray:
    return peak * np.sin(2 * np.pi * hz * T)


def _rest() -> FloatArray:
    """A forehead sensor at rest: alpha, a little noise, an offset."""
    return -54.0 + _sine(10, 20.0) + 2.0 * RNG.standard_normal(FS)


@pytest.mark.parametrize("hz", [35.0, 70.0, 90.0])
def test_the_level_of_a_sine_inside_the_band_is_its_rms(hz: float) -> None:
    assert tension_level(_sine(hz, 10.0)) == pytest.approx(10.0 / np.sqrt(2), rel=0.02)


def test_the_level_ignores_the_offset_and_what_lies_outside_the_band() -> None:
    assert tension_level(np.full(FS, -54.0) + _sine(10, 40.0)) < 0.5
    assert tension_level(_sine(20, 40.0)) < 0.5


def test_hum_and_the_device_lines_do_not_raise_the_level() -> None:
    rest = _rest()
    hum = rest + _sine(50, 30.0) + _sine(60, 30.0)
    lines = rest + sum(_sine(k * FS / 12, 3.0) for k in range(1, 7))
    assert tension_level(hum) < tension_level(rest) + 1.0
    assert tension_level(lines) < tension_level(rest) + 0.5
    assert tension_level(rest) < RULES.tension_uv


def test_the_smaller_of_two_sensors_in_use() -> None:
    forehead = np.column_stack([_rest() + _sine(40, 30.0), _rest() + _sine(40, 20.0)])
    mark, level = tension(forehead, (True, True))
    assert mark == "yes"
    assert level == pytest.approx(tension_level(forehead[:, 1]))


def test_one_sensor_in_use_gives_its_own_level() -> None:
    forehead = np.column_stack([_rest() + _sine(40, 30.0), _rest()])
    mark, level = tension(forehead, (True, False))
    assert (mark, level) == ("yes", pytest.approx(tension_level(forehead[:, 0])))
    mark, level = tension(forehead, (False, True))
    assert (mark, level) == ("no", pytest.approx(tension_level(forehead[:, 1])))


def test_with_no_forehead_sensor_in_use_tension_is_unavailable() -> None:
    forehead = np.column_stack([_rest(), _rest()])
    assert tension(forehead, (False, False)) == ("unavailable", None)


def test_a_level_at_the_limit_is_not_above_it() -> None:
    peak = RULES.tension_uv * np.sqrt(2)
    level = tension_level(_sine(70, peak))
    mark, _ = tension(np.column_stack([_sine(70, peak * 0.97)] * 2), (True, True))
    assert level == pytest.approx(RULES.tension_uv, rel=0.02)
    assert mark == "no"


def _judge(chunks: list[Chunk]) -> tuple[QualityAnswer, ...]:
    engine = QualityEngine()
    return engine.feed(chunks).answers + engine.finish().answers


def test_changing_tp9_or_tp10_changes_nothing() -> None:
    n = 6 * FS
    t = np.arange(n) / FS
    forehead = (
        -54.0 + 20.0 * np.sin(2 * np.pi * 10 * t)[:, None] + 8.0 * RNG.standard_normal((n, 2))
    )
    forehead[2 * FS : 4 * FS] += 30.0 * RNG.standard_normal((2 * FS, 2))  # a clench
    worn = 10.0 * RNG.standard_normal((n, 2))
    lifted = 300.0 * np.sin(2 * np.pi * 60 * t)[:, None] + 90.0 * RNG.standard_normal((n, 2))
    motion = np.zeros((6 * 52, 6))
    answers = []
    for ears in (worn, lifted):
        eeg = np.column_stack([ears[:, 0], forehead, ears[:, 1]])
        answers.append(_judge([eeg_chunk(eeg, 100.0), motion_chunk(motion, 100.0)]))
    same = [(a.tension, a.tension_uv, a.eye, a.movement) for a in answers[0]]
    assert same == [(a.tension, a.tension_uv, a.eye, a.movement) for a in answers[1]]
    assert [a.tension for a in answers[0]] == ["no", "no", "yes", "yes", "no", "no"]


def test_a_simulated_clench_is_marked(clock: FakeClock) -> None:
    reads = rehearse(replace(QUICK, clench=((3.0, 5.0),)), clock, 8.0)
    answers = _judge([c for read in reads for c in read if c.kind is not StreamKind.OPTICS])
    assert [a.tension for a in answers[:7]] == ["no", "no", "no", "yes", "yes", "no", "no"]
