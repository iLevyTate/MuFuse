"""Observations: a series held away from the wearer's baseline (006 decision 1).

The median z-score of the last 15 s must reach 2 to start one and fall under 1 to end it, so a
single odd second never starts one and a wobble near the limit never flickers. An observation is
a description of the signal; what it means is the wearer's to say.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

import numpy as np

from mufuse.features.engine import WITH_BASELINE, FeatureFrame

WINDOW_S = 15.0
START_Z, END_Z = 2.0, 1.0
NAMES = {
    "exponent": "spectral slope",
    "theta_share": "theta",
    "alpha_share": "alpha",
    "beta_share": "beta",
    "blinks_per_min": "blink rate",
    "hr_bpm": "heart rate",
    "rmssd_ms": "pulse variability",
}

Direction = Literal["higher", "lower"]


@dataclass(frozen=True)
class ObservationEvent:
    kind: Literal["start", "end"]
    series: str
    direction: Direction
    t: float
    since: float  # when the observation started

    @property
    def text(self) -> str:
        return f"{NAMES.get(self.series, self.series)} {self.direction} than usual"


class ObservationDetector:
    def __init__(self, series: tuple[str, ...] = WITH_BASELINE) -> None:
        self._series = series
        self._recent: dict[str, deque[tuple[float, float]]] = {s: deque() for s in series}
        self.active: dict[str, ObservationEvent] = {}  # series -> its start event

    def add(self, frame: FeatureFrame) -> list[ObservationEvent]:
        events: list[ObservationEvent] = []
        for series in self._series:
            recent = self._recent[series]
            z = frame.z.get(series)
            if z is not None:
                recent.append((frame.t, z))
            while recent and recent[0][0] <= frame.t - WINDOW_S:
                recent.popleft()
            if z is None or len(recent) < WINDOW_S / 2:  # needs half a window of values
                continue
            level = float(np.median([v for _, v in recent]))
            open_ = self.active.get(series)
            if open_ is None and abs(level) >= START_Z:
                way: Direction = "higher" if level > 0 else "lower"
                start = ObservationEvent("start", series, way, frame.t, frame.t)
                self.active[series] = start
                events.append(start)
            elif open_ is not None and (
                abs(level) < END_Z or (level > 0) != (open_.direction == "higher")
            ):
                del self.active[series]
                events.append(ObservationEvent("end", series, open_.direction, frame.t, open_.t))
        return events
