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
from mufuse.quality.answer import (
    SENSORS,
    Blink,
    ContactState,
    Coverage,
    QualityAnswer,
    SessionQuality,
)
from mufuse.quality.labelled import (
    KindScore,
    QuietScore,
    ScoreReport,
    labelled_guide,
    report_lines,
)
from mufuse.quality.rules import RULES_VERSION
from mufuse.quality.summary import summarize, summary_lines

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


def _summaries() -> list[list[str]]:
    """The inspect block for a session with every state and mark, and for one without data."""
    answers = []
    for i, (state, reason) in enumerate([("good", None), ("settling", None), *OUT[1:]]):
        contact = tuple(ContactState(n, state, reason, 50.0, 0.5) for n in SENSORS)  # type: ignore[arg-type]
        answers.append(
            QualityAnswer(
                start=100.0 + i,
                end=101.0 + i,
                rules=RULES_VERSION,
                contact=contact,
                coverage=Coverage("none", SENSORS),
                eye="yes",
                tension="yes",
                tension_uv=20.0,
                movement="moving",
            )
        )
    full = SessionQuality.of(tuple(answers), (Blink(101.0, 0.3),))
    empty = SessionQuality.of((QualityAnswer.gap(100.0, 103.0),), ())
    return [summary_lines(summarize(full)), summary_lines(summarize(empty))]


def _reports() -> list[ScoreReport]:
    passed = KindScore(20, 20, True)
    return [
        ScoreReport(
            RULES_VERSION, 2.0, passed, passed, passed,
            QuietScore(0.018, 0.0, 0.0, 2, True), KindScore(10, 10, True), True,
        ),
        ScoreReport(
            RULES_VERSION, 2.0, KindScore(17, 20, False), KindScore(0, 0, None), passed,
            QuietScore(None, None, None, 0, None, "more than 10% of the quiet stretches"),
            KindScore(8, 10, False), False,
        ),
    ]  # fmt: skip


def _texts() -> list[str]:
    texts = [NO_SENSOR, *COVERAGE_WORDS.values(), *SIGNAL_TEXTS.values()]
    texts += [template.format(name=n) for template in SENSOR_TEXTS.values() for n in SENSORS]
    for screen in _screens():
        texts += [coverage_line(screen, 200).plain, signal_line(screen, 200).plain]
        texts.append(screen.status_line())
    for lines in _summaries():
        texts += lines
    texts += [cue.text for cue in labelled_guide().cues]
    for report in _reports():
        texts += report_lines(report)
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
