"""`mufuse voice check` (007b) with a fake voice and recogniser on a fake clock."""

from __future__ import annotations

import numpy as np

from mufuse.voice.check import PHRASE, round_trip, words_right


def test_words_right_counts_the_phrase_words_heard_back() -> None:
    assert words_right("Blink rate is up.", "blink rate is up") == 1.0
    assert words_right("Blink rate is up.", "link rate is cup") == 0.5
    assert words_right("", "anything") == 0.0


def test_a_round_trip_times_speaking_and_hearing_apart() -> None:
    ticks = iter([0.0, 0.6, 0.85])
    result = round_trip(
        render=lambda text: (np.zeros(24_000 * 3, dtype=np.float32), 24_000),
        transcribe=lambda samples, rate: PHRASE.lower(),
        clock=lambda: next(ticks),
    )
    assert result.speak_s == 0.6
    assert result.audio_s == 3.0
    assert abs(result.hear_s - 0.25) < 1e-9
    assert result.words_right == 1.0
    text = "\n".join(result.lines())
    assert "real-time factor 0.20" in text
    assert "within the 1 s budget" in text
    assert "100% of the phrase" in text


def test_a_slow_recogniser_is_reported_over_budget_not_refused() -> None:
    ticks = iter([0.0, 1.0, 3.5])
    result = round_trip(
        lambda text: (np.zeros(16_000, dtype=np.float32), 16_000),
        lambda samples, rate: "",
        clock=lambda: next(ticks),
    )
    assert "over the 1 s budget" in "\n".join(result.lines())
    assert result.words_right == 0.0
