"""What the voice is given to say (007b)."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

from mufuse.chat.crisis import CRISIS_REPLY
from mufuse.voice.models import SPEAK
from mufuse.voice.speak import read_wav, reference, spoken


def test_web_addresses_are_said_as_words() -> None:
    assert spoken("See https://findahelpline.com for other countries.") == (
        "See findahelpline dot com for other countries."
    )


def test_the_crisis_reply_keeps_every_number_and_word() -> None:
    said = spoken(CRISIS_REPLY)
    assert "call or text nine eight eight" in said
    assert "call nine one one" in said
    assert "findahelpline dot com" in said


def test_markup_is_not_read_out() -> None:
    assert spoken("**Blink rate** is `up`.") == "Blink rate is up."


def test_a_wav_is_read_as_float_mono(tmp_path: Path) -> None:
    path = tmp_path / "v.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(24_000)
        w.writeframes(np.array([16384, 0, -16384, 0], dtype="<i2").tobytes())
    samples, rate = read_wav(path)
    assert rate == 24_000
    assert samples.tolist() == [0.5, -0.5]


def test_the_default_voice_is_the_first_reference_recording(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        reference(tmp_path)
    wavs = SPEAK.path(tmp_path) / "test_wavs"
    wavs.mkdir(parents=True)
    for name in ("b.wav", "a.wav"):
        (wavs / name).write_bytes(b"")
    assert reference(tmp_path).name == "a.wav"


def test_numbers_to_call_or_text_are_said_digit_by_digit() -> None:
    assert spoken("Call or text 988, any time.") == "Call or text nine eight eight, any time."
    assert spoken("If there is immediate danger: call 911.") == (
        "If there is immediate danger: call nine one one."
    )
    assert spoken("Blink rate is 12 a minute.") == "Blink rate is 12 a minute."
