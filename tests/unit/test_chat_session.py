"""A chat turn (007 decisions 1, 4-7): crisis first, a model behind the filter, else templates."""

from __future__ import annotations

import json
from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any

import pytest

from mufuse.chat.crisis import CRISIS_REPLY
from mufuse.chat.models import Claude, ModelUnavailableError, Ollama, Turn
from mufuse.chat.session import LATE, NIGHT_PER_HOUR, ChatSession
from mufuse.chat.summary import PARK, QUESTION_BACK, Summary, template_answer

GOOD = Summary(
    forehead_good=2,
    fix=None,
    line="blinks higher · alpha usual · heart rate steady",
    observations=(("blink rate higher than usual", 4.2),),
    last_answer="planning",
)


class Fake:
    def __init__(self, answer: str | None, *, cloud: bool = False, name: str = "fake") -> None:
        self.answer, self.cloud, self.name = answer, cloud, name
        self.seen: list[tuple[str, Sequence[Turn]]] = []

    def reply(self, system: str, turns: Sequence[Turn]) -> str:
        self.seen.append((system, list(turns)))
        if self.answer is None:
            raise ModelUnavailableError("down")
        return self.answer


def _session(*models: Fake, hour: int = 12) -> ChatSession:
    return ChatSession(lambda: models, clock=lambda: 1_800_000_000.0, hour_of=lambda _: hour)


def test_crisis_words_get_the_fixed_reply_and_no_model_sees_them() -> None:
    model = Fake("anything")
    reply = _session(model).ask("I want to end my life", GOOD)
    assert (reply.text, reply.source) == (CRISIS_REPLY, "crisis")
    assert model.seen == []


def test_a_model_words_the_answer_from_the_summary_only() -> None:
    model = Fake("Blink rate has been higher for about 4 minutes. Signal is good. What was up?")
    reply = _session(model).ask("what are you seeing?", GOOD)
    assert (reply.source, reply.model, reply.cloud) == ("model", "fake", False)
    system, turns = model.seen[0]
    assert "blink rate higher than usual for about 4 minutes" in system
    assert "Last check-in answer: planning" in system
    assert turns == [{"role": "user", "content": "what are you seeing?"}]


def test_a_blocked_reply_is_replaced_by_the_template_and_says_why() -> None:
    reply = _session(Fake("You are clearly anxious.")).ask("what are you seeing?", GOOD)
    assert reply.source == "filtered"
    assert reply.blocked == ("about the person",)
    assert reply.text == template_answer(GOOD)


def test_cloud_failing_falls_back_to_local_then_to_templates() -> None:
    reply = _session(Fake(None, cloud=True), Fake("Signal is good.", name="local")).ask("hi", GOOD)
    assert (reply.model, reply.cloud) == ("local", False)
    reply = _session(Fake(None), Fake(None)).ask("hi", GOOD)
    assert (reply.source, reply.text) == ("template", template_answer(GOOD))


def test_after_a_heavy_answer_it_parks_instead_of_asking_back() -> None:
    reply = _session().ask("my dad died last month and I can't cope", GOOD)
    assert PARK in reply.text
    assert QUESTION_BACK not in reply.text


def test_late_at_night_replies_are_limited() -> None:
    session = _session(hour=1)
    replies = [session.ask("hello", GOOD) for _ in range(NIGHT_PER_HOUR + 1)]
    assert replies[-1].text == LATE
    assert all(r.text != LATE for r in replies[:-1])
    assert _session(hour=14).ask("hello", GOOD).text != LATE


def test_the_conversation_is_remembered_for_the_model() -> None:
    model = Fake("Signal is good.")
    session = _session(model)
    session.ask("first", GOOD)
    session.ask("second", GOOD)
    turns = model.seen[-1][1]
    assert [t["content"] for t in turns] == ["first", "Signal is good.", "second"]


# Templates ------------------------------------------------------------------------------------


def test_poor_signal_says_so_and_names_the_sensor() -> None:
    text = template_answer(Summary(forehead_good=0, fix="AF7", line="fix AF7 first: no readings"))
    assert "fix AF7" in text
    assert QUESTION_BACK not in text


def test_a_quiet_baseline_says_nothing_stands_out() -> None:
    text = template_answer(Summary(forehead_good=2, fix=None, line="blinks usual"))
    assert text.startswith("Nothing stands out against your baseline: blinks usual.")
    assert text.endswith(QUESTION_BACK)


# Adapters -------------------------------------------------------------------------------------


class _Response:
    def __init__(self, body: dict[str, Any]) -> None:
        self._body = json.dumps(body).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *a: object) -> None:
        pass


def test_ollama_sends_the_system_rules_first_and_reads_the_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, Any]] = []

    def urlopen(request: Any, timeout: float) -> _Response:
        sent.append(json.loads(request.data))
        return _Response({"message": {"content": "Signal is good."}})

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    assert (
        Ollama(model="m").reply("rules", [{"role": "user", "content": "hi"}]) == "Signal is good."
    )
    assert sent[0]["messages"][0] == {"role": "system", "content": "rules"}
    assert sent[0]["stream"] is False


def test_ollama_not_running_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error

    def refuse(request: Any, timeout: float) -> None:
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", refuse)
    with pytest.raises(ModelUnavailableError, match="Ollama"):
        Ollama().reply("rules", [])


def _claude(content: list[Any], stop: str = "end_turn") -> tuple[Claude, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []

    def create(**kwargs: Any) -> Any:
        calls.append(kwargs)
        return SimpleNamespace(stop_reason=stop, content=content)

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    return Claude(client=client), calls


def test_claude_gets_the_summary_with_fallbacks_on_and_low_effort() -> None:
    model, calls = _claude(
        [SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text="Ok.")]
    )
    assert model.reply("rules", [{"role": "user", "content": "hi"}]) == "Ok."
    (call,) = calls
    assert call["model"] == "claude-opus-5-5"
    assert call["system"] == "rules"
    assert call["fallbacks"] == "default"
    assert call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["output_config"] == {"effort": "low"}
    assert model.cloud is True


def test_a_claude_refusal_or_error_is_unavailable() -> None:
    model, _ = _claude([], stop="refusal")
    with pytest.raises(ModelUnavailableError, match="declined"):
        model.reply("rules", [])

    def boom(**kwargs: Any) -> Any:
        raise RuntimeError("no credentials")

    broken = Claude(
        client=SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=boom)))
    )
    with pytest.raises(ModelUnavailableError, match="no credentials"):
        broken.reply("rules", [])


def test_the_model_is_asked_for_plain_text() -> None:
    model = Fake("Signal is good.")
    _session(model).ask("hi", GOOD)
    assert "no Markdown" in model.seen[0][0]
