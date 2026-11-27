"""Contact per sensor and coverage, once per stretch (contracts/quality-rules.md, section 2)."""

from __future__ import annotations

import numpy as np
import pytest

from mufuse.acquisition.contact import grade_window
from mufuse.acquisition.types import Chunk
from mufuse.quality.answer import SENSORS, Coverage, QualityAnswer
from mufuse.quality.engine import Judged, QualityEngine
from mufuse.quality.rules import RULES_VERSION
from tests.conftest import eeg_chunk, motion_chunk

FS, MOTION_HZ = 256, 52
T = np.arange(FS) / FS
RNG = np.random.default_rng(11)
T0 = 100.0


def _pattern() -> np.ndarray:
    return np.where(np.arange(FS) % 12 == 0, -3.0, 0.0)


def _good() -> np.ndarray:
    """Skin contact: a little noise, some hum, the offset of real data."""
    return 40.0 + 9.0 * RNG.standard_normal(FS) + 30.0 * np.sin(2 * np.pi * 60 * T) + _pattern()


def _hum() -> np.ndarray:
    """No skin contact: the input picks up the mains."""
    return 300.0 * np.sin(2 * np.pi * 60 * T) + 5.0 * RNG.standard_normal(FS) + _pattern()


def _loud() -> np.ndarray:
    """Touching, but the signal moves far more than a brain signal does."""
    drift = 160 * np.sin(2 * np.pi * 1.5 * T) + 90 * np.sin(2 * np.pi * 4 * T + 1)
    return drift + 60 * RNG.standard_normal(FS) + 20 * np.sin(2 * np.pi * 60 * T)


def _railed() -> np.ndarray:
    x = _good()
    x[40:120] = 725.0
    return x


def _flat() -> np.ndarray:
    return np.full(FS, 12.0)


def _floating() -> np.ndarray:
    dips = np.tile([-75.0, -675.0, -460.0, *[0.0] * 9], FS // 12 + 1)[:FS]
    return 115.0 + dips + 25.0 * RNG.standard_normal(FS)


def _second(**sensors: np.ndarray) -> np.ndarray:
    """One second of the four sensors: good contact, except those given by name."""
    return np.column_stack([sensors.get(name.lower(), _good()) for name in SENSORS])


def _chunks(seconds: list[np.ndarray], t0: float = T0) -> list[Chunk]:
    motion = np.zeros((MOTION_HZ * len(seconds), 6))
    return [eeg_chunk(np.concatenate(seconds), t0), motion_chunk(motion, t0)]


def _judge(*seconds: np.ndarray) -> tuple[QualityAnswer, ...]:
    engine = QualityEngine()
    return engine.feed(_chunks(list(seconds))).answers + engine.finish().answers


def _states(answers: tuple[QualityAnswer, ...], sensor: str) -> list[str]:
    return [a.state(sensor).state for a in answers if not a.no_data]


def _held(**sensors: np.ndarray) -> QualityAnswer:
    """The answer for one second that follows three seconds of good contact everywhere."""
    return _judge(_second(), _second(), _second(), _second(**sensors))[-1]


# One answer per stretch --------------------------------------------------------------------


def test_every_stretch_gets_one_answer_with_the_four_sensors() -> None:
    answers = _judge(_second(), _second())
    assert [(a.start, a.end) for a in answers] == [(100.0, 101.0), (101.0, 102.0)]
    for answer in answers:
        assert answer.rules == RULES_VERSION
        assert not answer.no_data
        assert tuple(c.sensor for c in answer.contact) == SENSORS


def test_nothing_is_judged_before_a_stretch_is_complete() -> None:
    engine = QualityEngine()
    assert engine.feed(_chunks([_second()])) == Judged(answers=(), blinks=())
    (answer,) = engine.finish().answers
    assert (answer.start, answer.end) == (100.0, 101.0)
    assert engine.finish() == Judged(answers=(), blinks=())


def test_an_answer_carries_what_was_measured() -> None:
    window = _hum()
    (answer,) = _judge(_second(tp9=window))
    reading = grade_window(window)
    assert reading is not None
    contact = answer.state("TP9")
    assert (contact.spread_uv, contact.mains_share) == (reading.spread_uv, reading.mains_share)
    assert contact.spread_uv > 75
    assert contact.mains_share > 0.6


# The hold ----------------------------------------------------------------------------------


def test_good_is_shown_from_the_third_good_stretch_in_a_row() -> None:
    answers = _judge(_second(), _second(), _second(), _second())
    for sensor in SENSORS:
        assert _states(answers, sensor) == ["settling", "settling", "good", "good"]
        assert all(a.state(sensor).reason is None for a in answers)


@pytest.mark.parametrize(("fault", "state"), [(_loud, "noisy"), (_hum, "none")])
def test_a_stretch_that_is_not_good_shows_at_once_and_sets_the_count_back(
    fault: object, state: str
) -> None:
    seconds = [_second() for _ in range(3)]
    seconds.append(_second(af7=fault()))  # type: ignore[operator]
    seconds += [_second() for _ in range(3)]
    answers = _judge(*seconds)
    assert _states(answers, "AF7") == [
        *("settling", "settling", "good"),
        state,
        *("settling", "settling", "good"),
    ]
    assert _states(answers, "AF8") == ["settling", "settling", *["good"] * 5]  # each on its own


def test_a_gap_sets_the_count_back_for_every_sensor() -> None:
    before = _chunks([_second() for _ in range(3)])
    after = _chunks([_second() for _ in range(3)], t0=110.0)
    engine = QualityEngine()
    answers = engine.feed(before + after).answers + engine.finish().answers
    assert [a.no_data for a in answers] == [False, False, False, True, False, False, False]
    gap = answers[3]
    assert (gap.start, gap.end) == (103.0, 110.0)
    assert gap == QualityAnswer.gap(103.0, 110.0)
    for sensor in SENSORS:
        assert _states(answers, sensor) == ["settling", "settling", "good"] * 2


# Reasons -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fault", "state", "reason"),
    [
        (_flat, "none", "flat"),
        (_railed, "none", "railed"),
        (_hum, "none", "hum"),
        (_floating, "none", "floating"),
        (_loud, "noisy", "loud"),
    ],
)
def test_every_fault_has_its_reason(fault: object, state: str, reason: str) -> None:
    answer = _held(tp10=fault())  # type: ignore[operator]
    contact = answer.state("TP10")
    assert (contact.state, contact.reason) == (state, reason)
    assert answer.reasons("TP10")[0] == f"{state}:{reason}"
    assert answer.state("AF7").state == "good"


def test_no_contact_is_told_apart_from_touching_but_noisy() -> None:
    answer = _held(af7=_hum(), af8=_loud())
    assert answer.state("AF7").state == "none"
    assert answer.state("AF8").state == "noisy"


def test_a_sensor_without_numbers_gives_a_flat_signal() -> None:
    mostly = _good()
    mostly[:200] = np.nan
    few = _good()
    few[:10] = np.nan
    answer = _held(tp9=np.full(FS, np.nan), af7=mostly, af8=few)
    for sensor in ("TP9", "AF7"):
        contact = answer.state(sensor)
        assert (contact.state, contact.reason) == ("none", "flat")
        assert (contact.spread_uv, contact.mains_share) == (0.0, 0.0)
    assert answer.state("AF8").state == "good"  # a few missing samples do not matter


# How fast a loss shows ---------------------------------------------------------------------


@pytest.mark.parametrize("lost_after", [5.0, 5.3, 5.9])
def test_a_loss_of_contact_shows_within_two_seconds(lost_after: float) -> None:
    eeg = np.concatenate([_second() for _ in range(5)] + [_second(af7=_hum()) for _ in range(4)])
    worn = round(lost_after * FS)
    eeg[5 * FS : worn, 1] = _good()[: worn - 5 * FS]  # AF7 lifts in the middle of a stretch
    engine = QualityEngine()
    shown_at: float | None = None
    for read in range(9 * 4):  # as a headband delivers it: a quarter of a second at a time
        first, last = read * 64, (read + 1) * 64
        chunks = [
            eeg_chunk(eeg[first:last], T0 + first / FS),
            motion_chunk(np.zeros((13, 6)), T0 + read * 13 / MOTION_HZ),
        ]
        states = [a.state("AF7").state for a in engine.feed(chunks).answers]
        if shown_at is None and "none" in states:
            shown_at = last / FS
    assert shown_at is not None
    assert shown_at - lost_after <= 2.0


# Coverage ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("lost", "level", "out"),
    [
        ((), "full", ()),
        (("TP9",), "reduced", ("TP9",)),
        (("TP10", "TP9"), "reduced", ("TP9", "TP10")),
        (("AF7",), "one_forehead", ("AF7",)),
        (("TP10", "AF8", "TP9"), "one_forehead", ("TP9", "AF8", "TP10")),
        (("AF8", "AF7"), "none", ("AF7", "AF8")),
    ],
)
def test_coverage_has_four_levels_and_names_the_sensors_that_are_out(
    lost: tuple[str, ...], level: str, out: tuple[str, ...]
) -> None:
    answer = _held(**{name.lower(): _hum() for name in lost})
    assert answer.coverage == Coverage(level, out)  # pyright: ignore[reportArgumentType]


def test_a_noisy_or_settling_sensor_is_out_as_well() -> None:
    seconds = [_second(), _second(), _second(), _second(tp10=_loud(), af7=_loud()), _second()]
    answers = _judge(*seconds)
    assert answers[0].coverage == Coverage("none", SENSORS)  # nothing is good before the hold
    assert answers[3].coverage == Coverage("one_forehead", ("AF7", "TP10"))
    assert _states(answers, "AF7")[4] == "settling"
    assert answers[4].coverage == Coverage("one_forehead", ("AF7", "TP10"))


def test_a_headband_that_is_not_worn_has_no_coverage() -> None:
    off = {name.lower(): _floating() for name in SENSORS}
    answers = _judge(_second(**off), _second(**off), _second(**off), _second(**off))
    for answer in answers:
        assert answer.coverage == Coverage("none", SENSORS)
        assert {(c.state, c.reason) for c in answer.contact} == {("none", "floating")}
        assert not any(answer.clean(sensor) for sensor in SENSORS)
