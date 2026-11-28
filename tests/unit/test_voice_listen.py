"""Where a spoken turn ends (007b), with a fake VAD that hears loud samples as speech."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np

from mufuse.voice.listen import RATE_HZ, WINDOW, capture

QUIET_WINDOWS = 25  # this many quiet windows after speech end a segment (0.8 s at 16 kHz)


class FakeVad:
    def __init__(self) -> None:
        self.windows: list[bool] = []
        self.segments: list[np.ndarray] = []
        self._current: list[np.ndarray] = []
        self._quiet = 0

    def accept_waveform(self, samples: Any) -> None:
        loud = bool(np.max(np.abs(samples)) > 0.1)
        self.windows.append(loud)
        if loud:
            self._current.append(np.asarray(samples))
            self._quiet = 0
        elif self._current:
            self._quiet += 1
            if self._quiet >= QUIET_WINDOWS:
                self.flush()

    def is_speech_detected(self) -> bool:
        return bool(self._current)

    def empty(self) -> bool:
        return not self.segments

    def flush(self) -> None:
        if self._current:
            self.segments.append(np.concatenate(self._current))
            self._current = []

    @property
    def front(self) -> Any:
        return SimpleNamespace(samples=self.segments[0])

    def pop(self) -> None:
        self.segments.pop(0)


def _chunks(*parts: tuple[float, float]) -> list[np.ndarray]:
    """(seconds, level) pieces cut into 0.1 s chunks."""
    audio = np.concatenate([np.full(int(s * RATE_HZ), lvl, dtype=np.float32) for s, lvl in parts])
    step = RATE_HZ // 10
    return [audio[i : i + step] for i in range(0, audio.size, step)]


def test_the_turn_ends_at_the_silence_after_speech() -> None:
    vad = FakeVad()
    got = capture(iter(_chunks((0.5, 0.0), (1.5, 0.5), (1.0, 0.0), (2.0, 0.5))), vad)
    assert got is not None
    # only the first utterance: 1.5 s, give or take the windows it starts and ends inside
    assert 1.5 * RATE_HZ <= got.size <= 1.5 * RATE_HZ + 2 * WINDOW
    assert len(vad.windows) < int(4.0 * RATE_HZ) // WINDOW  # the later speech is never read


def test_nothing_said_gives_nothing_after_the_wait() -> None:
    chunks = _chunks((30.0, 0.0))
    vad = FakeVad()
    assert capture(iter(chunks), vad, no_speech_s=2.0) is None
    assert len(vad.windows) <= int(2.1 * RATE_HZ) // WINDOW


def test_speech_still_going_at_the_limit_is_taken_as_it_is() -> None:
    vad = FakeVad()
    got = capture(iter(_chunks((0.2, 0.0), (5.0, 0.5))), vad, max_s=3.0)
    assert got is not None
    assert 2.5 * RATE_HZ < got.size <= 3.0 * RATE_HZ
