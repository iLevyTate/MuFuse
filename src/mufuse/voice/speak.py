# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Speaking (007b): Pocket TTS through sherpa-onnx, played on the default output.

Pocket TTS words any text with its own front end, so nothing in a reply is skipped. It speaks in
the voice of a short reference recording; the default is one shipped with the model package.
"""

from __future__ import annotations

import re
import wave
from pathlib import Path

import numpy as np

from mufuse.voice.models import SPEAK

STEPS = 5  # Pocket TTS flow steps: more is slower and a little clearer
DIGITS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
# a number to call or text is said the way hotlines are said: "nine eight eight", not "988"
_TO_DIAL = re.compile(r"\b((?:call|text)(?:\s+or\s+(?:call|text))?\s+)(\d{3,})\b", re.IGNORECASE)


def spoken(text: str) -> str:
    """The reply as it should sound: web addresses and numbers to call as words, no markup."""
    text = re.sub(r"https?://", "", text)
    text = re.sub(r"\b([a-z0-9-]+)\.(com|org|net)\b", r"\1 dot \2", text)
    text = _TO_DIAL.sub(lambda m: m[1] + " ".join(DIGITS[int(d)] for d in m[2]), text)
    return re.sub(r"[*_`#]+", "", text).strip()


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """A 16-bit WAV as float32 mono in [-1, 1], and its rate."""
    with wave.open(str(path), "rb") as w:
        rate, channels = w.getframerate(), w.getnchannels()
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    return (raw.reshape(-1, channels)[:, 0].astype(np.float32) / 32768.0), rate


def reference(root: Path) -> Path:
    """The default voice: the first recording in the model package's `test_wavs`."""
    wavs = sorted((SPEAK.path(root) / "test_wavs").glob("*.wav"))
    if not wavs:
        raise FileNotFoundError(f"no reference voice in {SPEAK.path(root) / 'test_wavs'}")
    return wavs[0]


class Voice:  # pragma: no cover - needs the model and a sound card (`mufuse voice check`)
    def __init__(self, root: Path, voice: Path | None = None) -> None:
        import sherpa_onnx

        m = SPEAK.path(root)
        config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                pocket=sherpa_onnx.OfflineTtsPocketModelConfig(
                    lm_flow=str(m / "lm_flow.int8.onnx"),
                    lm_main=str(m / "lm_main.int8.onnx"),
                    encoder=str(m / "encoder.onnx"),
                    decoder=str(m / "decoder.int8.onnx"),
                    text_conditioner=str(m / "text_conditioner.onnx"),
                    vocab_json=str(m / "vocab.json"),
                    token_scores_json=str(m / "token_scores.json"),
                ),
                num_threads=2,
                provider="cpu",
            )
        )
        if not config.validate():
            raise RuntimeError(f"the speech model in {m} is incomplete: run mufuse voice fetch")
        self._tts = sherpa_onnx.OfflineTts(config)
        self._gen = sherpa_onnx.GenerationConfig()
        samples, rate = read_wav(voice or reference(root))
        self._gen.reference_audio = samples
        self._gen.reference_sample_rate = rate
        self._gen.num_steps = STEPS

    def render(self, text: str) -> tuple[np.ndarray, int]:
        audio = self._tts.generate(spoken(text), self._gen)
        return np.asarray(audio.samples, dtype=np.float32), int(audio.sample_rate)

    def say(self, text: str) -> None:
        import sounddevice as sd

        samples, rate = self.render(text)
        if samples.size:
            sd.play(samples, rate)
            sd.wait()
