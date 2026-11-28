"""The "now against your baseline" line (005 decision 6): words for the signal, never the person."""

from __future__ import annotations

import pytest

from mufuse.companion.describe import baseline_line, word


@pytest.mark.parametrize(
    ("z", "expected"),
    [
        (0.3, "usual"),
        (-0.9, "usual"),
        (1.4, "a little higher"),
        (-1.0, "a little lower"),
        (2.0, "higher"),
        (-3.5, "lower"),
        (None, None),
    ],
)
def test_z_scores_become_plain_words(z: float | None, expected: str | None) -> None:
    assert word(z) == expected


def test_the_line_names_blinks_alpha_and_heart_rate() -> None:
    line = baseline_line({"blinks_per_min": 2.4, "alpha_share": -0.2, "hr_bpm": 0.1}, fix=None)
    assert line == "blinks higher · alpha usual · heart rate steady"


def test_a_series_without_a_baseline_yet_is_left_out() -> None:
    line = baseline_line({"blinks_per_min": None, "alpha_share": 1.2, "hr_bpm": None}, fix=None)
    assert line == "alpha a little higher"


def test_before_any_baseline_it_says_so() -> None:
    assert baseline_line({}, fix=None) == "learning your baseline"


def test_poor_signal_names_the_sensor_and_shows_no_reading() -> None:
    assert baseline_line({"blinks_per_min": 3.0}, fix="AF7") == "fix AF7 first: no readings"


def test_no_word_ever_describes_the_person() -> None:
    banned = ("you", "anxious", "calm", "stress", "focus", "relax", "tired", "mood")
    for z in (-4.0, -1.5, 0.0, 1.5, 4.0):
        line = baseline_line({"blinks_per_min": z, "alpha_share": z, "hr_bpm": z}, fix=None)
        assert not any(b in line.lower() for b in banned), line
