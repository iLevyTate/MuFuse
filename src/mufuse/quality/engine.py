"""Judges a session stretch by stretch: one answer for every second of signal and every gap.

The engine reads samples and their timestamps and nothing else: no clock, no file, no network.
The same samples give the same answers, however they were delivered (contracts/quality-rules.md).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from mufuse.acquisition.contact import grade_window
from mufuse.acquisition.types import Chunk, FloatArray, StreamKind
from mufuse.quality.answer import (
    FOREHEAD,
    SENSORS,
    Blink,
    ContactState,
    QualityAnswer,
    Reason,
    SessionQuality,
    State,
    coverage_of,
)
from mufuse.quality.blink import EyeDetector
from mufuse.quality.motion import movement
from mufuse.quality.rules import RULES, Rules
from mufuse.quality.stretch import NoData, Stretch, StretchCutter
from mufuse.quality.tension import tension
from mufuse.recording.reader import LoadedSession

_FOREHEAD_COLUMNS = [SENSORS.index(name) for name in FOREHEAD]  # AF7, AF8; TP9, TP10 never read
JUDGE_STEP_S = 10.0  # a recording is fed in pieces of this long, in time order


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
        self._eye = EyeDetector(rules)

    def feed(self, chunks: Sequence[Chunk]) -> Judged:
        return self._judge(self._cutter.add(chunks))

    def finish(self) -> Judged:
        """The stretches that still wait, judged with the samples that exist."""
        judged = self._judge(self._cutter.finish())
        return Judged(judged.answers, judged.blinks + self._eye.close())

    def settle_left(self, sensor: str) -> int:
        """Good stretches `sensor` still needs, after the newest one, before it shows as good."""
        return max(self._rules.hold_stretches - self._good[sensor], 0)

    def _judge(self, items: Sequence[Stretch | NoData]) -> Judged:
        answers: list[QualityAnswer] = []
        blinks: list[Blink] = []
        for item in items:
            if isinstance(item, NoData):
                self._good = dict.fromkeys(SENSORS, 0)  # a gap ends every hold
                blinks += self._eye.close()  # ... and the eye's run; a new anchor follows
                answers.append(QualityAnswer.gap(item.start, item.end))
            else:
                answer, found = self._answer(item)
                answers.append(answer)
                blinks += found
        return Judged(answers=tuple(answers), blinks=tuple(blinks))

    def _answer(self, stretch: Stretch) -> tuple[QualityAnswer, tuple[Blink, ...]]:
        contact = tuple(
            self._contact(name, stretch.eeg[:, column]) for column, name in enumerate(SENSORS)
        )
        by = {c.sensor: c for c in contact}
        in_use = tuple(by[name].state != "none" for name in FOREHEAD)  # rules section 3
        eye, blinks = self._eye.judge(stretch, in_use)
        mark, level = tension(stretch.eeg[:, _FOREHEAD_COLUMNS], in_use, self._rules)
        answer = QualityAnswer(
            start=stretch.start,
            end=stretch.end,
            rules=self._rules.version,
            contact=contact,
            coverage=coverage_of(contact),
            eye=eye,
            tension=mark,
            tension_uv=level,
            movement=movement(stretch.motion, self._rules),
        )
        return answer, blinks

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


def judge(session: LoadedSession, rules: Rules = RULES) -> SessionQuality:
    """The answers for a recorded session, the same as live (the recording is only read)."""
    engine = QualityEngine(rules)
    answers: list[QualityAnswer] = []
    blinks: list[Blink] = []
    streams = [
        (kind, ts, data)
        for kind, (ts, data) in session.streams.items()
        if kind in (StreamKind.EEG, StreamKind.MOTION) and ts.size
    ]
    if streams:
        first = min(float(ts[0]) for _, ts, _ in streams)
        last = max(float(ts[-1]) for _, ts, _ in streams)
        steps = int((last - first) // JUDGE_STEP_S) + 1
        edges = first + JUDGE_STEP_S * np.arange(steps + 1)
        edges[-1] = np.inf
        cuts = [np.searchsorted(ts, edges) for _, ts, _ in streams]
        for step in range(steps):
            chunks = [
                Chunk(kind, ts[cut[step] : cut[step + 1]], data[cut[step] : cut[step + 1]])
                for (kind, ts, data), cut in zip(streams, cuts, strict=True)
                if cut[step + 1] > cut[step]
            ]
            judged = engine.feed(chunks)
            answers += judged.answers
            blinks += judged.blinks
    judged = engine.finish()
    return SessionQuality.of((*answers, *judged.answers), (*blinks, *judged.blinks), rules.version)
