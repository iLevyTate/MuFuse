"""One voice turn (007b), with a fake microphone and voice."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mufuse.chat.crisis import CRISIS_REPLY
from mufuse.voice.turn import voice_turn


class Heard:
    def __init__(self, words: str) -> None:
        self.words = words

    def listen(self) -> str:
        return self.words


class Voice:
    def __init__(self, log: list[str], fail: bool = False) -> None:
        self.log, self.fail = log, fail

    def say(self, text: str) -> None:
        if self.fail:
            raise RuntimeError("no sound card")
        self.log.append(f"spoken: {text}")


def test_the_words_heard_go_to_ask_and_the_reply_is_shown_then_spoken() -> None:
    log: list[str] = []
    asked: list[str] = []

    def ask(text: str) -> Mapping[str, Any]:
        asked.append(text)
        return {"type": "chat", "reply": "Blink rate is up on your baseline.", "cloud": False}

    heard = voice_turn(Heard(" what are you seeing? "), Voice(log), ask, log.append)
    assert heard == "what are you seeing?"
    assert asked == ["what are you seeing?"]
    assert log == [
        "Listening…",
        "heard: what are you seeing?",
        "Blink rate is up on your baseline.",
        "spoken: Blink rate is up on your baseline.",
    ]


def test_nothing_heard_asks_nothing() -> None:
    log: list[str] = []
    assert voice_turn(Heard("  "), Voice(log), lambda _: {}, log.append) is None
    assert log == ["Listening…", "Nothing heard."]


def test_the_crisis_reply_is_shown_in_full_even_when_speech_fails() -> None:
    log: list[str] = []
    voice_turn(
        Heard("I want to end it"),
        Voice(log, fail=True),
        lambda _: {"type": "chat", "reply": CRISIS_REPLY, "crisis": True},
        log.append,
    )
    assert CRISIS_REPLY in log
    assert log.index(CRISIS_REPLY) < len(log) - 1
    assert log[-1] == "(could not speak the reply: no sound card)"


def test_a_cloud_reply_is_badged_on_screen_but_the_badge_is_not_spoken() -> None:
    log: list[str] = []
    voice_turn(Heard("hi"), Voice(log), lambda _: {"reply": "Hello.", "cloud": True}, log.append)
    assert "Hello. [cloud]" in log
    assert log[-1] == "spoken: Hello."


def test_without_a_voice_the_reply_is_only_shown() -> None:
    log: list[str] = []
    voice_turn(Heard("hi"), None, lambda _: {"error": "the engine is busy"}, log.append)
    assert log[-1] == "the engine is busy"
