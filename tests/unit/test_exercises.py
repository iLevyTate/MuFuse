"""The exercise scripts (009): load, timing, and wording that never speaks about the person."""

from __future__ import annotations

import pytest

from mufuse.chat.filter import check
from mufuse.exercises.library import EXERCISES, load


@pytest.mark.parametrize("name", EXERCISES)
def test_each_script_loads_in_time_order_and_runs_three_to_five_minutes(name: str) -> None:
    exercise = load(name)
    assert exercise.id == name
    ats = [at for at, _ in exercise.steps]
    assert ats == sorted(ats)
    assert ats[0] == 0.0
    assert 180.0 <= exercise.duration_s <= 300.0
    assert ats[-1] < exercise.duration_s


@pytest.mark.parametrize("name", EXERCISES)
def test_no_line_makes_a_claim_or_speaks_about_the_person(name: str) -> None:
    for _, text in load(name).steps:  # through the 007 output filter, like any chat reply
        assert check(text).ok, (text, check(text).reasons)


@pytest.mark.parametrize("name", EXERCISES)
def test_the_guide_marks_start_and_end_in_a_recording(name: str) -> None:
    guide = load(name).guide()
    markers = [c.marker for c in guide.cues if c.marker]
    assert markers == [f"x:{name}:start", f"x:{name}:end"]


def test_an_unknown_exercise_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown exercise"):
        load("hypnosis")
