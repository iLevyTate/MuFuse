"""The check before a guided run: is the headband on well enough to begin?"""

from __future__ import annotations

from mufuse.acquisition.contact import SensorView
from mufuse.preflight import WAIT_S, Preflight


def _sensors(**shown: str) -> tuple[SensorView, ...]:
    states = {"TP9": "good", "AF7": "good", "AF8": "good", "TP10": "good"} | shown
    return tuple(SensorView(name, state, None) for name, state in states.items())  # type: ignore[arg-type]


def test_it_is_ready_once_both_forehead_sensors_are_good_and_motion_flows() -> None:
    check = Preflight()
    assert check.phase(_sensors(), motion=True, elapsed=2.0) == "ready"


def test_the_ears_never_hold_it_up() -> None:  # issue #12
    check = Preflight()
    assert check.phase(_sensors(TP9="none", TP10="noisy"), motion=True, elapsed=2.0) == "ready"


def test_it_waits_while_a_forehead_sensor_settles_or_motion_is_missing() -> None:
    check = Preflight()
    assert check.phase(_sensors(AF7="settling"), motion=True, elapsed=1.0) == "waiting"
    assert check.phase(_sensors(), motion=False, elapsed=1.0) == "waiting"
    assert check.phase(_sensors(AF8="waiting"), motion=True, elapsed=1.0) == "waiting"


def test_after_the_wait_the_wearer_decides_but_a_late_fit_still_starts_it() -> None:
    check = Preflight()
    assert check.phase(_sensors(AF7="none"), motion=True, elapsed=WAIT_S) == "decide"
    assert check.phase(_sensors(), motion=True, elapsed=WAIT_S + 5) == "ready"


def test_the_outcome_names_what_is_out_and_says_the_ears_are_only_noted() -> None:
    lines = Preflight().outcome(_sensors(AF7="none", TP9="noisy"), motion=True, anyway=True)
    text = "\n".join(lines)
    assert "Started without a full fit" in text
    assert "AF7 is not connected" in text
    assert "TP9 is noisy" in text
    assert "ear sensors are noted only" in text


def test_a_clean_fit_says_so_in_one_line() -> None:
    assert Preflight().outcome(_sensors(), motion=True, anyway=False) == (
        "Pre-flight: all four EEG sensors good, motion streaming. Starting.",
    )


def test_the_marker_label_is_short_and_names_what_was_out() -> None:
    check = Preflight()
    assert check.marker(_sensors(), anyway=False) == "check:ready"
    assert check.marker(_sensors(TP10="none"), anyway=False) == "check:ready:TP10"
    assert check.marker(_sensors(AF7="none", TP9="noisy"), anyway=True) == "check:anyway:TP9,AF7"


def test_the_guide_tells_the_wearer_what_to_do_and_which_keys_work() -> None:
    check = Preflight()
    text, _ = check.guide(deciding=False).current(0.0)
    assert "AF7" in text
    assert "AF8" in text
    assert "s = start anyway" in text
    text, _ = check.guide(deciding=True).current(0.0)
    assert "s = start anyway" in text
    assert "q = stop" in text
