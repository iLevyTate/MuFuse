"""`mufuse voice check` (007b): how long speaking and hearing take on this computer.

The voice says a fixed phrase, the recogniser writes it back down, and both are timed. No
microphone is needed, so it measures the models, not the room. The 1 s budget is 007's fast-loop
figure; replies are in the slow loop, so a slower result is reported, not refused.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

PHRASE = "Blink rate is up on your baseline. The signal is clear on both forehead sensors."
BUDGET_S = 1.0


@dataclass(frozen=True)
class CheckResult:
    phrase: str
    heard: str
    speak_s: float  # time to render the phrase
    audio_s: float  # how long the phrase lasts
    hear_s: float  # time to write it back down
    words_right: float  # share of the phrase's words found in what was heard

    def lines(self) -> list[str]:
        rtf = self.speak_s / self.audio_s if self.audio_s else float("inf")
        within = "within" if self.hear_s <= BUDGET_S else "over"
        return [
            f"Speaking: {self.speak_s:.2f} s to render {self.audio_s:.1f} s of speech"
            f" (real-time factor {rtf:.2f})",
            f"Hearing:  {self.hear_s:.2f} s to write it down ({within} the {BUDGET_S:g} s budget)",
            f"Heard:    {self.heard!r}",
            f"Words:    {self.words_right:.0%} of the phrase heard back",
        ]


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def words_right(said: str, heard: str) -> float:
    want, got = _words(said), set(_words(heard))
    return sum(w in got for w in want) / len(want) if want else 0.0


def round_trip(
    render: Callable[[str], tuple[np.ndarray, int]],
    transcribe: Callable[[np.ndarray, int], str],
    phrase: str = PHRASE,
    clock: Callable[[], float] = time.perf_counter,
) -> CheckResult:
    t0 = clock()
    samples, rate = render(phrase)
    t1 = clock()
    heard = transcribe(samples, rate)
    t2 = clock()
    audio_s = samples.size / rate if rate else 0.0
    return CheckResult(phrase, heard, t1 - t0, audio_s, t2 - t1, words_right(phrase, heard))
