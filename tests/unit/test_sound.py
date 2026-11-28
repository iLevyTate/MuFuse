"""The tone a wearer hears with eyes closed."""

from __future__ import annotations

import sys

import pytest

from mufuse import sound

_real_beep = sound._beep  # pyright: ignore[reportPrivateUsage]  # before conftest silences it


def test_the_tone_plays_without_holding_up_the_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    played: list[bool] = []
    monkeypatch.setattr(sound, "_beep", lambda: played.append(True))
    sound.tone().join(timeout=2)
    assert played == [True]


@pytest.mark.skipif(sys.platform != "win32", reason="the sound card tone is Windows only")
def test_on_windows_the_tone_goes_to_the_sound_card(monkeypatch: pytest.MonkeyPatch) -> None:
    import winsound

    played: list[tuple[int, int]] = []
    monkeypatch.setattr(winsound, "Beep", lambda hz, ms: played.append((hz, ms)))  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    _real_beep()
    assert played == [(sound.TONE_HZ, sound.TONE_MS)]


@pytest.mark.skipif(sys.platform != "win32", reason="the sound card tone is Windows only")
def test_a_machine_without_sound_stays_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    import winsound

    def refuse(hz: int, ms: int) -> None:
        raise RuntimeError("Failed to beep")

    monkeypatch.setattr(winsound, "Beep", refuse)
    _real_beep()  # no error reaches the run loop
