"""007 inside `mufuse serve`: ask, the cloud switch, speaking first, and the fast loop."""

from __future__ import annotations

import threading
import time
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from mufuse.acquisition.simulated import Rehearsal
from mufuse.chat.crisis import CRISIS_REPLY
from mufuse.chat.models import Model, Turn
from mufuse.companion.serve import Engine
from mufuse.companion.store import Store
from mufuse.features.engine import FeatureFrame
from tests.conftest import FakeClock
from tests.integration.test_companion_serve import RESTING, Caught, _run


class Slow:
    name, cloud = "slow", False

    def __init__(self, seconds: float = 0.0, answer: str = "Signal is good.") -> None:
        self.seconds, self.answer = seconds, answer
        self.started = threading.Event()

    def reply(self, system: str, turns: Sequence[Turn]) -> str:
        self.started.set()
        time.sleep(self.seconds)
        return self.answer


def _engine(
    tmp_path: Path, model: Slow | None = None
) -> tuple[Engine, FakeClock, Caught, list[bool]]:
    clock = FakeClock()
    rehearsal = Rehearsal(RESTING, clock=clock, sleep=clock.advance)
    asked_cloud: list[bool] = []

    def models(cloud: bool) -> Sequence[Model]:
        asked_cloud.append(cloud)
        return [model] if model else []

    engine = Engine(
        rehearsal.source,
        Store(tmp_path / "db"),
        clock,
        np.random.default_rng(0),
        models=models,
        mean_wait_s=100.0,
        spacing_s=60.0,
    )
    caught = Caught(engine)
    engine.start()
    return engine, clock, caught, asked_cloud


def test_ask_returns_the_reply_and_publishes_it(tmp_path: Path) -> None:
    engine, clock, caught, _ = _engine(tmp_path, Slow())
    _run(engine, clock, 10.0)
    reply = engine.command({"type": "ask", "text": "what are you seeing?"})
    assert (reply["type"], reply["reply"], reply["source"]) == ("ok", "Signal is good.", "model")
    assert caught.of("chat")[-1]["text"] == "Signal is good."
    engine.stop()


def test_crisis_words_get_the_fixed_reply_through_serve(tmp_path: Path) -> None:
    engine, *_ = _engine(tmp_path, Slow())
    reply = engine.command({"type": "ask", "text": "I want to kill myself"})
    assert (reply["reply"], reply["source"]) == (CRISIS_REPLY, "crisis")
    engine.stop()


def test_cloud_is_off_until_switched_on_and_remembered(tmp_path: Path) -> None:
    engine, _, _, asked_cloud = _engine(tmp_path, Slow())
    engine.command({"type": "ask", "text": "hi"})
    assert engine.command({"type": "cloud", "on": True})["cloud"] is True
    engine.command({"type": "ask", "text": "hi"})
    assert asked_cloud == [False, True]
    assert engine.store.setting("cloud") == "on"
    assert engine.hello()["cloud"] is True  # the app's toggle starts where it was left
    engine.stop()


def test_it_speaks_first_at_start_after_an_answer_on_an_observation_and_at_the_end(
    tmp_path: Path,
) -> None:
    engine, clock, caught, _ = _engine(tmp_path)
    _run(engine, clock, 3.0)
    engine.command({"type": "checkin"})
    (asked,) = caught.of("checkin")
    engine.command({"type": "answer", "id": asked["id"], "answer": "planning"})
    for z in [0.0] * 20 + [3.0] * 20:
        clock.advance(1.0)
        engine._on_frame(FeatureFrame(t=clock.now, values={}, z={"blinks_per_min": z}))  # pyright: ignore[reportPrivateUsage]
    engine.stop()
    said = [m["text"] for m in caught.of("chat")]
    assert said[0].startswith("I'm here.")
    assert "Noted: planning." in said
    assert any(s.startswith("Blink rate higher than usual.") for s in said)
    assert said[-1].startswith("Session ended: 1 of 1 check-ins answered, 1 observations")
    assert all(m["source"] == "template" and m["cloud"] is False for m in caught.of("chat"))


def test_a_slow_model_never_holds_up_the_headband_loop(tmp_path: Path) -> None:
    """The fast-loop gate: steps (check-ins, observations) go on while the chat waits."""
    model = Slow(seconds=1.5)
    engine, clock, _, _ = _engine(tmp_path, model)
    thread = threading.Thread(target=engine.command, args=({"type": "ask", "text": "hi"},))
    thread.start()
    assert model.started.wait(2.0)
    started = time.perf_counter()
    _run(engine, clock, 5.0)  # 20 steps while the model is still busy
    took = time.perf_counter() - started
    still_busy = thread.is_alive()
    thread.join()
    engine.stop()
    assert still_busy
    assert took < 1.0, f"{took:.2f} s"


def test_mufuse_chat_talks_to_a_running_engine(tmp_path: Path, monkeypatch) -> None:
    from typer.testing import CliRunner

    from mufuse.cli import app
    from mufuse.companion.serve import Server

    engine, *_ = _engine(tmp_path, Slow(answer="Signal is good on 2 of 2 forehead sensors."))
    server = Server(engine)
    server.start()
    path = server.write_serve_file(tmp_path / "serve.json")
    monkeypatch.setattr("mufuse.chat.client.serve_file", lambda: path)
    try:
        result = CliRunner().invoke(app, ["chat", "--cloud"], input="what are you seeing?\n\n")
    finally:
        server.stop()
        engine.stop()
    assert result.exit_code == 0, result.output
    assert "Cloud on" in result.output
    assert "Signal is good on 2 of 2 forehead sensors." in result.output
    assert engine.store.setting("cloud") == "on"


def test_mufuse_chat_without_an_engine_says_how_to_start_it(tmp_path: Path, monkeypatch) -> None:
    from typer.testing import CliRunner

    from mufuse.cli import EXIT_CONNECT, app

    monkeypatch.setattr("mufuse.chat.client.serve_file", lambda: tmp_path / "none.json")
    result = CliRunner().invoke(app, ["chat"])
    assert result.exit_code == EXIT_CONNECT
    assert "uv run mufuse serve" in result.output
