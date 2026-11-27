from __future__ import annotations

from pathlib import Path

import pytest

from mufuse.guide import READY_S, Cue, Guide, action, guide_from_env


def _guide() -> Guide:
    return Guide(
        cues=(Cue(0, "Sit still"), *action(15, "Turn the headband OFF", marker="power_off")),
        duration=60,
    )


def test_action_counts_down_before_the_instruction() -> None:
    ready, now = action(15, "Turn the headband OFF", marker="power_off")
    assert ready.at == 15 - READY_S
    assert "get ready" in ready.text.lower()
    assert ready.marker is None
    assert now.at == 15
    assert now.marker == "power_off"


def test_prompt_shows_the_current_cue_and_time_to_the_next() -> None:
    guide = _guide()
    assert guide.prompt(0.0) == "Sit still · 12 s"
    assert guide.prompt(12.2) == "Get ready: Turn the headband OFF · 3 s"
    assert guide.prompt(14.1) == "Get ready: Turn the headband OFF · 1 s"
    assert guide.prompt(15.0).startswith(">> Turn the headband OFF")
    assert guide.prompt(15.0).endswith("· 45 s")


def test_prompt_uses_minutes_for_long_steps_and_says_when_done() -> None:
    guide = Guide(cues=(Cue(0, "Sit still"),), duration=600)
    assert guide.prompt(1.0) == "Sit still · 9:59"
    assert guide.prompt(600.0) == "Done, stopping"


def test_markers_fire_once_at_their_scheduled_time() -> None:
    guide = _guide()
    assert guide.due(14.9) == []
    assert guide.due(16.0) == [("power_off", 15.0)]
    assert guide.due(30.0) == []


def test_json_round_trip_and_env_loading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "guide.json"
    _guide().save(path)
    assert Guide.load(path).cues == _guide().cues
    assert guide_from_env() is None
    monkeypatch.setenv("MUFUSE_GUIDE", str(path))
    loaded = guide_from_env()
    assert loaded is not None
    assert loaded.duration == 60


def test_timeline_marks_done_now_next_and_later_steps() -> None:
    guide = Guide(
        cues=(
            Cue(0, "Sit still"),
            *action(15, "Turn the headband OFF", marker="power_off"),
            *action(30, "Turn the headband ON", marker="power_on"),
        ),
        duration=60,
        title="H5 · Power-cycle recovery",
    )
    assert guide.timeline(13.0) == [
        (0, "Sit still", "now"),
        (15, "Turn the headband OFF", "next"),
        (30, "Turn the headband ON", "later"),
    ]
    assert [state for _, _, state in guide.timeline(16.0)] == ["done", "now", "next"]
    assert [state for _, _, state in guide.timeline(60.0)] == ["done", "done", "done"]


def test_clock_shows_elapsed_and_total() -> None:
    guide = Guide(cues=(Cue(0, "Sit still"),), duration=75)
    assert guide.clock(23.4) == "0:23 / 1:15"
    assert guide.clock(99.0) == "1:15 / 1:15"


def test_title_survives_a_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "guide.json"
    Guide(cues=(Cue(0, "Sit still"),), duration=10, title="H4 · Completeness").save(path)
    assert Guide.load(path).title == "H4 · Completeness"


def test_current_gives_the_bare_instruction_and_the_seconds_left_in_it() -> None:
    guide = _guide()
    assert guide.current(0.0) == ("Sit still", 12.0)
    assert guide.current(12.5) == ("Get ready: Turn the headband OFF", 2.5)
    assert guide.current(20.0) == (
        "Turn the headband OFF",
        40.0,
    )  # no ">>" or "now": the view says NOW
    assert guide.current(60.0) == ("Done, stopping", 0.0)
    assert Guide(cues=(Cue(5, "Later"),), duration=10).current(1.0) == ("Starting", 4.0)


def test_a_cue_can_ring_the_bell_once() -> None:
    guide = Guide(cues=(Cue(0, "Eyes closed"), Cue(10, "Open your eyes", bell=True)), duration=20)
    assert guide.bells(9.9) == 0
    assert guide.bells(10.0) == 1
    assert guide.bells(15.0) == 0  # once
