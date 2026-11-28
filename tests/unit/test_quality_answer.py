"""The answer for one stretch, and what later features read from it (data-model.md)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from mufuse.acquisition import contact, signal_check
from mufuse.quality.answer import SENSORS, Blink, ContactState, Coverage, QualityAnswer, Span
from mufuse.quality.rules import RULES, RULES_VERSION, Rules

GOOD = tuple(ContactState(name, "good", None, 14.0, 0.1) for name in SENSORS)
CLEAN = QualityAnswer(
    start=10.0,
    end=11.0,
    rules=RULES_VERSION,
    contact=GOOD,
    coverage=Coverage("full", ()),
    eye="no",
    tension="no",
    tension_uv=4.8,
    movement="still",
)


def _with(sensor: str, state: str, reason: str | None) -> QualityAnswer:
    changed = tuple(
        replace(c, state=state, reason=reason) if c.sensor == sensor else c  # pyright: ignore[reportArgumentType]
        for c in GOOD
    )
    return replace(CLEAN, contact=changed)


def test_the_rules_are_version_1_and_cannot_be_changed_in_place() -> None:
    assert RULES_VERSION == "1"
    assert RULES.version == RULES_VERSION
    assert Rules() == RULES
    with pytest.raises(FrozenInstanceError):
        RULES.tension_uv = 99.0  # pyright: ignore[reportAttributeAccessIssue]


def test_the_rules_hold_the_limits_of_the_contract() -> None:
    assert (RULES.stretch_n, RULES.gap_s, RULES.ahead_n, RULES.motion_wait_s) == (
        256,
        0.25,
        64,
        1.0,
    )
    assert RULES.hold_stretches == 3
    assert (RULES.eye_band_hz, RULES.envelope_n, RULES.limit_s, RULES.limit_every_n) == (
        (1.0, 10.0),
        32,
        30.0,
        8,
    )
    assert (RULES.eye_mad_factor, RULES.eye_floor_uv) == (4.0, 15.0)
    assert (RULES.eye_min_n, RULES.blink_max_n, RULES.blink_apart_s, RULES.eye_warmup) == (
        16,
        307,
        0.8,
        5,
    )
    assert RULES.eye_margin_n == 32
    assert RULES.tension_bands_hz == ((30, 48), (66, 98))
    assert RULES.tension_skip_hz == (42, 43, 44, 84, 85, 86)
    assert RULES.tension_uv == 10.0
    assert (RULES.motion_min_n, RULES.gyro_dps, RULES.acc_std_g) == (26, 20.0, 0.05)


def test_the_contact_limits_are_those_of_the_grade_that_is_reused() -> None:
    assert RULES.rail_uv == signal_check.RAIL_UV == 710.5
    assert RULES.rail_share == signal_check.RAIL_FRACTION
    assert RULES.flat_uv == signal_check.FLAT_UV
    assert RULES.noisy_uv == signal_check.NOISY_UV
    assert RULES.mains_share == contact.MAINS_SHARE
    assert RULES.gap_s == 0.25
    assert SENSORS == contact.SENSORS == ("TP9", "AF7", "AF8", "TP10")


def test_a_clean_stretch_has_no_disturbance_and_no_reason() -> None:
    assert CLEAN.disturbances == ()
    assert not CLEAN.no_data
    for sensor in SENSORS:
        assert CLEAN.clean(sensor)
        assert CLEAN.reasons(sensor) == ()


def test_disturbances_come_in_a_fixed_order() -> None:
    marked = replace(CLEAN, movement="moving", tension="yes", eye="yes")
    assert marked.disturbances == ("eye", "tension", "movement")
    unknown = replace(CLEAN, movement="unknown", tension="unavailable", eye="unavailable")
    assert unknown.disturbances == ("eye_unavailable", "tension_unavailable", "movement_unknown")
    mixed = replace(CLEAN, movement="moving", eye="unavailable")
    assert mixed.disturbances == ("movement", "eye_unavailable")


def test_a_disturbance_makes_every_sensor_not_clean() -> None:
    blink = replace(CLEAN, eye="yes")
    assert not blink.clean("AF7")
    assert blink.reasons("AF7") == ("eye",)
    assert blink.reasons("TP9") == ("eye",)


def test_a_sensor_that_is_not_good_is_not_clean_and_says_why() -> None:
    answer = replace(_with("TP9", "none", "hum"), tension="yes")
    assert not answer.clean("TP9")
    assert answer.reasons("TP9") == ("none:hum", "tension")
    assert answer.reasons("AF7") == ("tension",)
    assert _with("AF7", "noisy", "loud").reasons("AF7") == ("noisy:loud",)
    assert _with("AF8", "settling", None).reasons("AF8") == ("settling",)
    assert _with("AF8", "settling", None).clean("AF7")
    assert _with("AF7", "noisy", "loud").state("AF7").reason == "loud"


def test_an_answer_does_not_know_other_sensors() -> None:
    with pytest.raises(KeyError):
        CLEAN.state("AUX1")


def test_a_no_data_answer_covers_a_gap_and_gives_one_reason() -> None:
    gap = QualityAnswer.gap(13.0, 15.4)
    assert (gap.start, gap.end, gap.no_data, gap.rules) == (13.0, 15.4, True, RULES_VERSION)
    assert gap.contact == ()
    assert gap.coverage == Coverage("none", SENSORS)
    assert (gap.eye, gap.tension, gap.tension_uv, gap.movement) == (
        "unavailable",
        "unavailable",
        None,
        "unknown",
    )
    assert gap.disturbances == ("no_data",)
    for sensor in SENSORS:
        assert not gap.clean(sensor)
        assert gap.reasons(sensor) == ("no_data",)


def test_blinks_and_spans_are_plain_values() -> None:
    assert Blink(12.41, 0.27) == Blink(t=12.41, duration_s=0.27)
    assert Span("movement", 20.0, 22.0) == Span(kind="movement", start=20.0, end=22.0)
    with pytest.raises(FrozenInstanceError):
        Blink(1.0, 0.2).t = 2.0  # pyright: ignore[reportAttributeAccessIssue]
