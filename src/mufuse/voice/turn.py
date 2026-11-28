"""One voice turn (007b): hear the question, send it as text, show the reply, then speak it.

Every part is passed in, so the order can be tested without a microphone or a model. The reply
is always shown before it is spoken, and a voice that fails leaves the text standing: the crisis
reply must never wait for, or depend on, speech.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol


class Listener(Protocol):
    def listen(self) -> str:
        """Block until one spoken turn has ended; its words, or "" when nothing was heard."""
        ...


class Speaker(Protocol):
    def say(self, text: str) -> None: ...


def reply_text(reply: Mapping[str, Any]) -> str:
    """What the engine answered, or the error it gave."""
    return str(reply.get("reply") or reply.get("error") or "No reply.")


def voice_turn(
    listener: Listener,
    speaker: Speaker | None,
    ask: Callable[[str], Mapping[str, Any]],
    show: Callable[[str], None],
) -> str | None:
    """Hear, ask, show, speak. Returns the words heard, or None when nothing was heard."""
    show("Listening…")
    heard = listener.listen().strip()
    if not heard:
        show("Nothing heard.")
        return None
    show(f"heard: {heard}")
    say(ask(heard), speaker, show)
    return heard


def say(reply: Mapping[str, Any], speaker: Speaker | None, show: Callable[[str], None]) -> None:
    """Show the reply first (with the cloud badge), then speak it if there is a voice."""
    text = reply_text(reply)
    show(text + (" [cloud]" if reply.get("cloud") else ""))
    if speaker is None:
        return
    try:
        speaker.say(text)
    except Exception as exc:  # the text stands; speech is extra
        show(f"(could not speak the reply: {exc})")
