"""The tone a wearer hears with eyes closed, on any computer."""

from __future__ import annotations

import io
import subprocess
import sys
import wave
from pathlib import Path

import pytest

from mufuse import sound

_real_beep = sound._beep  # pyright: ignore[reportPrivateUsage]  # before conftest silences it


def test_the_tone_plays_without_holding_up_the_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    played: list[bool] = []
    monkeypatch.setattr(sound, "_beep", lambda: played.append(True))
    sound.tone().join(timeout=2)
    assert played == [True]


def test_the_tone_is_a_short_mono_wave_any_player_reads() -> None:
    with wave.open(io.BytesIO(sound.tone_wav()), "rb") as w:
        assert (w.getnchannels(), w.getsampwidth()) == (1, 2)
        assert w.getnframes() / w.getframerate() == pytest.approx(sound.TONE_MS / 1000, abs=0.01)


@pytest.mark.parametrize(
    ("platform", "found", "expected"),
    [
        ("darwin", {"afplay"}, ["afplay"]),
        ("linux", {"paplay", "aplay"}, ["paplay"]),  # PulseAudio and PipeWire desktops first
        ("linux", {"pw-play", "aplay"}, ["pw-play"]),
        ("linux", {"aplay"}, ["aplay", "-q"]),
        ("linux", set[str](), None),  # no player: the terminal bell is all there is
        ("freebsd14", {"aplay"}, ["aplay", "-q"]),
    ],
)
def test_each_system_plays_the_file_with_the_player_it_has(
    platform: str, found: set[str], expected: list[str] | None
) -> None:
    which = lambda name: f"/usr/bin/{name}" if name in found else None  # noqa: E731
    command = sound.player(platform, which)
    if expected is None:
        assert command is None
    else:
        assert command is not None
        assert command[0] == f"/usr/bin/{expected[0]}"
        assert command[1:] == expected[1:]


def test_a_player_gets_the_tone_as_a_file(monkeypatch: pytest.MonkeyPatch) -> None:
    ran: list[list[str]] = []

    def run(cmd: list[str], **kwargs: object) -> None:
        ran.append(cmd)
        assert Path(cmd[-1]).read_bytes() == sound.tone_wav()  # the file exists while it plays

    monkeypatch.setattr(sound, "player", lambda *_: ["/usr/bin/afplay"])
    monkeypatch.setattr(subprocess, "run", run)
    sound.play_with_player("darwin")
    assert len(ran) == 1
    assert not Path(ran[0][-1]).exists()  # and is gone afterwards


@pytest.mark.parametrize("error", [OSError("no such device"), subprocess.TimeoutExpired("x", 5)])
def test_a_player_that_fails_leaves_the_run_loop_alone(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def run(cmd: list[str], **kwargs: object) -> None:
        raise error

    monkeypatch.setattr(sound, "player", lambda *_: ["/usr/bin/aplay", "-q"])
    monkeypatch.setattr(subprocess, "run", run)
    sound.play_with_player("linux")  # no error reaches the caller


def test_without_a_player_nothing_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sound, "player", lambda *_: None)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("ran"))  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    sound.play_with_player("linux")


@pytest.mark.skipif(sys.platform != "win32", reason="winsound exists on Windows only")
def test_on_windows_the_tone_goes_to_the_sound_card_from_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import winsound

    played: list[tuple[bytes, int]] = []
    monkeypatch.setattr(winsound, "PlaySound", lambda data, flags: played.append((data, flags)))  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    _real_beep()
    assert played == [(sound.tone_wav(), winsound.SND_MEMORY)]


@pytest.mark.skipif(sys.platform != "win32", reason="winsound exists on Windows only")
def test_a_windows_machine_without_sound_stays_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    import winsound

    def refuse(data: bytes, flags: int) -> None:
        raise RuntimeError("Failed to play sound")

    monkeypatch.setattr(winsound, "PlaySound", refuse)
    _real_beep()  # no error reaches the run loop


@pytest.mark.skipif(sys.platform == "win32", reason="the player path is for macOS and Linux")
def test_elsewhere_the_tone_goes_to_the_player(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []
    monkeypatch.setattr(sound, "play_with_player", called.append)
    _real_beep()
    assert called == [sys.platform]
