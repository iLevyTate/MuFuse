# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Hearing (007b): the microphone at 16 kHz, Silero VAD ends the turn, Moonshine writes it down.

The microphone is open only while a turn is heard. The audio stays in memory and is dropped when
the words are out; nothing is written to disk.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from mufuse.voice.models import HEAR, VAD

RATE_HZ = 16_000
CHUNK_S = 0.1
WINDOW = 512  # samples per VAD step (Silero)
SILENCE_S = 0.8  # the turn ends after this much quiet
MAX_TURN_S = 20.0
NO_SPEECH_S = 8.0  # nothing said this long after Enter: nothing heard


class Vad(Protocol):
    """What `capture` needs of sherpa-onnx's VoiceActivityDetector."""

    def accept_waveform(self, samples: Any) -> None: ...
    def is_speech_detected(self) -> bool: ...
    def empty(self) -> bool: ...
    def flush(self) -> None: ...
    @property
    def front(self) -> Any: ...  # a segment with `.samples`
    def pop(self) -> None: ...


def capture(
    chunks: Iterable[np.ndarray],
    vad: Vad,
    max_s: float = MAX_TURN_S,
    no_speech_s: float = NO_SPEECH_S,
) -> np.ndarray | None:
    """The first spoken segment in `chunks` (float32 at 16 kHz), or None if nothing was said."""
    buffered = np.zeros(0, dtype=np.float32)
    heard_s, spoke = 0.0, False
    for chunk in chunks:
        heard_s += chunk.size / RATE_HZ
        buffered = np.concatenate([buffered, chunk.astype(np.float32)])
        while buffered.size >= WINDOW:
            vad.accept_waveform(buffered[:WINDOW])
            buffered = buffered[WINDOW:]
        spoke = spoke or vad.is_speech_detected()
        if not vad.empty():
            return np.asarray(vad.front.samples, dtype=np.float32)
        if (not spoke and heard_s >= no_speech_s) or heard_s >= max_s:
            break
    vad.flush()  # speech still going when time ran out: take what there is
    if spoke and not vad.empty():
        return np.asarray(vad.front.samples, dtype=np.float32)
    return None


class Hearing:  # pragma: no cover - needs the models and a microphone (`mufuse voice check`)
    """The microphone, the VAD and the recogniser, loaded once."""

    def __init__(self, root: Path, small: bool = False) -> None:
        import sherpa_onnx

        model = HEAR["small" if small else "base"].path(root)
        self._recogniser = sherpa_onnx.OfflineRecognizer.from_moonshine_v2(
            encoder=str(model / "encoder_model.ort"),
            decoder=str(model / "decoder_model_merged.ort"),
            tokens=str(model / "tokens.txt"),
            num_threads=2,
        )
        self._vad_config = sherpa_onnx.VadModelConfig()
        self._vad_config.silero_vad.model = str(VAD.path(root))
        self._vad_config.silero_vad.min_silence_duration = SILENCE_S
        self._vad_config.silero_vad.max_speech_duration = MAX_TURN_S
        self._vad_config.silero_vad.window_size = WINDOW
        self._vad_config.sample_rate = RATE_HZ
        self._sherpa = sherpa_onnx

    def transcribe(self, samples: np.ndarray, rate: int = RATE_HZ) -> str:
        stream = self._recogniser.create_stream()
        stream.accept_waveform(rate, samples)
        self._recogniser.decode_stream(stream)
        return str(stream.result.text).strip()

    def listen(self) -> str:
        import sounddevice as sd

        vad = self._sherpa.VoiceActivityDetector(self._vad_config, buffer_size_in_seconds=30)
        block = int(RATE_HZ * CHUNK_S)
        with sd.InputStream(
            channels=1, dtype="float32", samplerate=RATE_HZ, blocksize=block
        ) as mic:

            def chunks() -> Iterator[np.ndarray]:
                while True:
                    data, _ = mic.read(block)
                    yield np.asarray(data[:, 0])

            samples = capture(chunks(), vad)
        return "" if samples is None else self.transcribe(samples)
