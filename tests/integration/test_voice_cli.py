"""`mufuse chat --voice` and `mufuse voice` (007b), with a fake microphone and voice."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from typer.testing import CliRunner

from mufuse.chat.crisis import CRISIS_REPLY
from mufuse.cli import EXIT_NONE_FOUND, app
from mufuse.companion.serve import Server
from mufuse.voice.models import models_dir
from tests.integration.test_chat_serve import Slow, _engine


class Ears:
    def __init__(self, *turns: str) -> None:
        self.turns = list(turns)

    def listen(self) -> str:
        return self.turns.pop(0)

    def transcribe(self, samples: np.ndarray, rate: int) -> str:
        return "blink rate is up on your baseline"


class Mouth:
    def __init__(self) -> None:
        self.said: list[str] = []

    def say(self, text: str) -> None:
        self.said.append(text)

    def render(self, text: str) -> tuple[np.ndarray, int]:
        return np.zeros(16_000, dtype=np.float32), 16_000


@pytest.fixture
def loopback_only(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Every connection the test makes; any but 127.0.0.1 fails it (survey 3.8 egress check)."""
    seen: list[Any] = []
    real = socket.socket.connect

    def connect(self: socket.socket, address: Any) -> Any:
        seen.append(address)
        assert address[0] in ("127.0.0.1", "::1"), f"voice path reached {address}"
        return real(self, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    return seen


def _serving(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, answer: str):
    engine, *_ = _engine(tmp_path, Slow(answer=answer))
    server = Server(engine)
    server.start()
    path = server.write_serve_file(tmp_path / "serve.json")
    monkeypatch.setattr("mufuse.chat.client.serve_file", lambda: path)
    return engine, server


def test_a_spoken_question_is_asked_as_text_and_the_reply_spoken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, loopback_only: list[Any]
) -> None:
    ears, mouth = Ears("what are you seeing", "I want to end it all"), Mouth()
    monkeypatch.setattr("mufuse.cli._load_voice", lambda small: (ears, mouth))
    engine, server = _serving(tmp_path, monkeypatch, "Signal is good on 2 of 2 forehead sensors.")
    try:
        result = CliRunner().invoke(app, ["chat", "--voice"], input="\n\ntyped too\nq\n")
    finally:
        server.stop()
        engine.stop()
    assert result.exit_code == 0, result.output
    out = result.output
    assert "Press Enter and speak" in out
    assert "heard: what are you seeing" in out
    assert "heard: I want to end it all" in out
    assert "call or text 988" in out  # the crisis path is unchanged by voice
    assert "findahelpline.com" in out
    assert mouth.said[0] == "Signal is good on 2 of 2 forehead sensors."
    assert mouth.said[1] == CRISIS_REPLY
    assert len(mouth.said) == 3  # the typed question's reply is spoken as well
    assert loopback_only  # it did talk to the engine, and only there


def test_chat_voice_without_the_models_says_how_to_fetch_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    try:
        import sherpa_onnx  # noqa: F401  # pyright: ignore[reportUnusedImport]
        import sounddevice  # noqa: F401  # pyright: ignore[reportUnusedImport]
    except (ImportError, OSError) as exc:  # no PortAudio on a bare Linux runner
        pytest.skip(f"no voice extra here: {exc}")
    monkeypatch.setattr("mufuse.voice.models.models_dir", lambda: tmp_path / "Models")
    engine, server = _serving(tmp_path, monkeypatch, "ok")
    try:
        result = CliRunner().invoke(app, ["chat", "--voice"])
    finally:
        server.stop()
        engine.stop()
    assert result.exit_code == EXIT_NONE_FOUND
    assert "uv run mufuse voice fetch" in result.output


def test_voice_check_prints_the_timings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("mufuse.cli._load_voice", lambda small: (Ears(), Mouth()))
    result = CliRunner().invoke(app, ["voice", "check"])
    assert result.exit_code == 0, result.output
    assert "Speaking:" in result.output
    assert "Hearing:" in result.output


def test_voice_fetch_puts_the_models_in_the_user_data_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fetched: list[str] = []

    def fake_fetch(model: Any, root: Path, say: Any = None) -> Path:
        fetched.append(model.name)
        return root / model.name

    monkeypatch.setattr("mufuse.voice.models.models_dir", lambda: tmp_path)
    monkeypatch.setattr("mufuse.voice.models.fetch", fake_fetch)
    result = CliRunner().invoke(app, ["voice", "fetch", "--small"])
    assert result.exit_code == 0, result.output
    assert fetched[0] == "silero_vad.onnx"
    assert len(fetched) == 4
    assert models_dir().name == "Models"


MODELS = models_dir()


@pytest.mark.skipif(
    not (MODELS / "silero_vad.onnx").exists(), reason="speech models not fetched on this computer"
)
def test_the_real_models_hear_back_what_they_said(loopback_only: list[Any]) -> None:
    """On a computer with the models (`mufuse voice fetch`): a real round trip, no network."""
    pytest.importorskip("sherpa_onnx")
    from mufuse.voice.check import round_trip
    from mufuse.voice.listen import Hearing
    from mufuse.voice.speak import Voice

    result = round_trip(Voice(MODELS).render, Hearing(MODELS).transcribe)
    assert result.words_right >= 0.7, result.lines()
    assert loopback_only == []
