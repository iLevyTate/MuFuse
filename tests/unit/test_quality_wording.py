"""Every quality text describes a sensor or a signal, never the person (FR-018, FR-019, SC-009).

Each story adds the texts it can show to `_texts()`.
"""

from __future__ import annotations

import re

import pytest

from mufuse.acquisition.contact import Reading, SensorView
from mufuse.acquisition.supervisor import State
from mufuse.live_view import (
    COVERAGE_WORDS,
    NO_SENSOR,
    SENSOR_TEXTS,
    SIGNAL_TEXTS,
    Screen,
    SignalMarks,
    coverage_line,
    signal_line,
)
from mufuse.quality.answer import SENSORS, Coverage

# Words that describe a state of the person rather than of a sensor or a signal.
PERSON_WORDS = (
    "anxious", "anxiety", "stress", "stressed", "tense", "tension", "nervous", "worried",
    "calm", "relaxed", "focused", "focus", "distracted", "attention", "tired", "sleepy",
    "drowsy", "fatigue", "fatigued", "mood", "emotion", "emotional", "happy", "sad", "angry",
    "frustrated", "overwhelmed", "mental", "mind", "you are", "you're", "you seem", "your brain",
)  # fmt: skip
PERSON = re.compile(r"\b(" + "|".join(re.escape(w) for w in PERSON_WORDS) + r")\b", re.IGNORECASE)

# What a sensor that is out shows, as (shown, why): every state and reason this story knows.
OUT = (
    ("settling", "quiet"),
    ("noisy", "loud"),
    ("none", "hum"),
    ("none", "railed"),
    ("none", "flat"),
    ("none", "floating"),
)


def _view(name: str, shown: str, why: str) -> SensorView:
    grade = "good" if shown in ("good", "settling") else shown
    return SensorView(name, shown, Reading(grade, why, 120.0, 0.9), 1)  # type: ignore[arg-type]


def _screen(
    sensors: tuple[SensorView, ...], coverage: Coverage | None, signal: SignalMarks | None = None
) -> Screen:
    return Screen(
        recording=None,
        elapsed=12.0,
        state=State.STREAMING,
        link_error=None,
        battery=80.0,
        device=None,
        sensors=sensors,
        streams=(),
        gaps=0,
        markers=0,
        glare=False,
        coverage=coverage,
        signal=signal,
    )


def _screens() -> list[Screen]:
    good = {name: _view(name, "good", "quiet") for name in SENSORS}
    screens = [
        _screen(tuple(good.values()), None),
        _screen(tuple(good.values()), Coverage("full", ())),
    ]
    for shown, why in OUT:
        for name in SENSORS:
            views = tuple(_view(n, shown, why) if n == name else good[n] for n in SENSORS)
            level = "one_forehead" if name in ("AF7", "AF8") else "reduced"
            screens.append(_screen(views, Coverage(level, (name,))))  # type: ignore[arg-type]
        every = tuple(_view(n, shown, why) for n in SENSORS)
        screens.append(_screen(every, Coverage("none", SENSORS)))
    for blinks in (None, 0, 1, 14):
        for tension in (False, True):
            for movement in ("still", "moving", "unknown"):
                marks = SignalMarks(blinks, tension, movement)  # type: ignore[arg-type]
                screens.append(_screen(tuple(good.values()), Coverage("full", ()), marks))
    return screens


def _texts() -> list[str]:
    texts = [NO_SENSOR, *COVERAGE_WORDS.values(), *SIGNAL_TEXTS.values()]
    texts += [template.format(name=n) for template in SENSOR_TEXTS.values() for n in SENSORS]
    for screen in _screens():
        texts += [coverage_line(screen, 200).plain, signal_line(screen, 200).plain]
        texts.append(screen.status_line())
    return texts


def test_the_word_list_catches_words_about_the_person() -> None:
    for words in ("You are tense", "you seem anxious", "stress level", "Mood: calm"):
        assert PERSON.search(words), words
    for words in ("AF7 is not touching skin (mostly mains hum)", "muscle activity in the signal"):
        assert not PERSON.search(words), words


@pytest.mark.parametrize("text", _texts())
def test_no_text_names_a_state_of_the_person(text: str) -> None:
    assert not PERSON.search(text), text


def test_every_sensor_text_starts_with_its_sensor() -> None:
    for template in SENSOR_TEXTS.values():
        for name in SENSORS:
            assert template.format(name=name).startswith(f"{name} ")
    assert "sensor" in NO_SENSOR
