"""Judges a session stretch by stretch: one answer for every second of signal and every gap.

The engine reads samples and their timestamps and nothing else: no clock, no file, no network.
The same samples give the same answers, however they were delivered (contracts/quality-rules.md).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from mufuse.acquisition.contact import grade_window
from mufuse.acquisition.types import Chunk, FloatArray
from mufuse.quality.answer import (
    SENSORS,
    Blink,
    ContactState,
    QualityAnswer,
    Reason,
    State,
    coverage_of,
)
from mufuse.quality.rules import RULES, Rules
from mufuse.quality.stretch import NoData, Stretch, StretchCutter


@dataclass(frozen=True)
class Judged:
    """What one call found: the stretches and gaps judged since the last call, in time order."""

    answers: tuple[QualityAnswer, ...] = ()
    blinks: tuple[Blink, ...] = ()


class QualityEngine:
    """Takes chunks as they come and gives back the answers that are final."""

    def __init__(self, rules: Rules = RULES) -> None:
        self._rules = rules
        self._cutter = StretchCutter(rules)
        self._good = dict.fromkeys(SENSORS, 0)  # good stretches in a row, per sensor

    def feed(self, chunks: Sequence[Chunk]) -> Judged:
        return self._judge(self._cutter.add(chunks))

    def finish(self) -> Judged:
        """The stretches that still wait, judged with the samples that exist."""
        return self._judge(self._cutter.finish())

    def settle_left(self, sensor: str) -> int:
        """Good stretches `sensor` still needs, after the newest one, before it shows as good."""
        return max(self._rules.hold_stretches - self._good[sensor], 0)

    def _judge(self, items: Sequence[Stretch | NoData]) -> Judged:
        answers: list[QualityAnswer] = []
        for item in items:
            if isinstance(item, NoData):
                self._good = dict.fromkeys(SENSORS, 0)  # a gap ends every hold
                answers.append(QualityAnswer.gap(item.start, item.end))
            else:
                answers.append(self._answer(item))
        return Judged(answers=tuple(answers))

    def _answer(self, stretch: Stretch) -> QualityAnswer:
        contact = tuple(
            self._contact(name, stretch.eeg[:, column]) for column, name in enumerate(SENSORS)
        )
        return QualityAnswer(
            start=stretch.start,
            end=stretch.end,
            rules=self._rules.version,
            contact=contact,
            coverage=coverage_of(contact),
            eye="unavailable",
            tension="unavailable",
            tension_uv=None,
            movement="unknown",
        )

    def _contact(self, sensor: str, window: FloatArray) -> ContactState:
        """The grade of one stretch, and `good` only from the third good stretch in a row."""
        reading = grade_window(window)
        if reading is None:  # more than half of the samples are not numbers
            self._good[sensor] = 0
            return ContactState(sensor, "none", "flat", 0.0, 0.0)
        spread, mains = float(reading.spread_uv), float(reading.mains_share)
        reason: Reason | None = None if reading.why == "quiet" else reading.why
        if reading.grade != "good":
            self._good[sensor] = 0
            return ContactState(sensor, reading.grade, reason, spread, mains)
        self._good[sensor] += 1
        held = self._good[sensor] >= self._rules.hold_stretches
        state: State = "good" if held else "settling"
        return ContactState(sensor, state, reason, spread, mains)
