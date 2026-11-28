"""A personal baseline per series: the rolling median and scaled MAD of what came before.

A z-score says how far the newest value sits from this wearer's own recent values; it says nothing
about other people and nothing about what the wearer feels (constitution III).
"""

from __future__ import annotations

from collections import deque

import numpy as np

from mufuse.features.params import PARAMS


class Baseline:
    def __init__(
        self, window_s: float = PARAMS.baseline_window_s, min_n: int = PARAMS.baseline_min_n
    ) -> None:
        self.window_s = window_s
        self.min_n = min_n
        self._values: deque[tuple[float, float]] = deque()
        self.median: float | None = None

    @property
    def count(self) -> int:
        return len(self._values)

    def add(self, value: float | None, *, t: float) -> float | None:
        """The z-score of `value` against the values before it, then `value` joins them."""
        while self._values and self._values[0][0] <= t - self.window_s:
            self._values.popleft()
        if value is None:
            return None
        z = None
        if len(self._values) >= self.min_n:
            past = np.fromiter((v for _, v in self._values), dtype=np.float64)
            median = float(np.median(past))
            spread = PARAMS.mad_scale * float(np.median(np.abs(past - median)))
            z = (value - median) / spread if spread > 0 else None
        self._values.append((t, value))
        self.median = float(np.median([v for _, v in self._values]))
        return z
