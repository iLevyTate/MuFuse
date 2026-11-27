"""Cuts the EEG and MOTION streams into stretches of one second, on sample time.

A stretch is 256 EEG samples in a row, counted from the first sample or from the first sample
after a gap. What a stretch holds depends on the samples only, never on how they were delivered.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from mufuse.acquisition.types import Chunk, FloatArray, StreamKind
from mufuse.quality.rules import RULES, Rules

EEG_COLUMNS, MOTION_COLUMNS = 4, 6
MOTION_KEPT_WITHOUT_EEG = 4096  # samples; motion from before the first EEG sample is never read


@dataclass(frozen=True)
class NoData:
    """A time without EEG samples: from the end of the last full stretch to the next sample."""

    start: float
    end: float


@dataclass(frozen=True, eq=False)
class Stretch:
    """One second of signal, ready to be judged."""

    start: float
    end: float
    index: int  # of its first sample, counted from the anchor
    t: FloatArray
    eeg: FloatArray  # (256, 4): TP9, AF7, AF8, TP10
    ahead_t: FloatArray
    ahead: FloatArray  # the 64 samples after the stretch; fewer before a gap and at the end
    motion: FloatArray  # (n, 6): the samples with start <= t < end


class StretchCutter:
    """Takes chunks as they come and gives back the stretches that can be judged."""

    def __init__(self, rules: Rules = RULES) -> None:
        self._rules = rules
        self._t: FloatArray = np.empty(0)
        self._x: FloatArray = np.empty((0, EEG_COLUMNS))
        self._motion_t: FloatArray = np.empty(0)
        self._motion: FloatArray = np.empty((0, MOTION_COLUMNS))
        self._index = 0  # of the first held EEG sample, counted from the anchor
        self._covered: float | None = None  # answers reach this far in the present run of samples

    @property
    def held_samples(self) -> int:
        return int(self._t.size + self._motion_t.size)

    def add(self, chunks: Sequence[Chunk]) -> list[Stretch | NoData]:
        """Store every chunk, then return what can be judged, in time order."""
        eeg = [c for c in chunks if c.kind is StreamKind.EEG]
        motion = [c for c in chunks if c.kind is StreamKind.MOTION]
        if eeg:
            self._t = np.concatenate([self._t, *(c.timestamps for c in eeg)])
            self._x = np.concatenate([self._x, *(c.data[:, :EEG_COLUMNS] for c in eeg)])
        if motion:
            self._motion_t = np.concatenate([self._motion_t, *(c.timestamps for c in motion)])
            self._motion = np.concatenate(
                [self._motion, *(c.data[:, :MOTION_COLUMNS] for c in motion)]
            )
        return self._cut(final=False)

    def finish(self) -> list[Stretch | NoData]:
        """The full stretches that still wait, with the samples that exist."""
        return self._cut(final=True)

    def _cut(self, *, final: bool) -> list[Stretch | NoData]:
        rules, t = self._rules, self._t
        if not t.size:
            self._trim(0)
            return []
        if self._covered is None:
            self._covered = float(t[0])
        newest_eeg = float(t[-1])
        newest_motion = float(self._motion_t[-1]) if self._motion_t.size else -np.inf
        gaps = np.flatnonzero(np.diff(t) > rules.gap_s) + 1  # rows that follow a gap
        out: list[Stretch | NoData] = []
        row = 0
        for stop in (*gaps.tolist(), t.size):
            closed = final or stop < t.size  # nothing more comes before `stop`
            while row + rules.stretch_n <= stop:
                last = row + rules.stretch_n
                end = float(t[row]) + 1.0
                ahead = min(last + rules.ahead_n, stop)
                if not closed and (
                    ahead - last < rules.ahead_n
                    or (newest_motion < end and newest_eeg < end + rules.motion_wait_s)
                ):
                    break
                out.append(self._stretch(row, last, ahead, end))
                self._index += rules.stretch_n
                self._covered = end
                row = last
            if stop == t.size:
                break
            out.append(NoData(self._covered, float(t[stop])))
            row, self._index, self._covered = stop, 0, float(t[stop])
        self._trim(row)
        return out

    def _stretch(self, row: int, last: int, ahead: int, end: float) -> Stretch:
        start = float(self._t[row])
        first, after = np.searchsorted(self._motion_t, [start, end], side="left")
        return Stretch(
            start=start,
            end=end,
            index=self._index,
            t=self._t[row:last],
            eeg=self._x[row:last],
            ahead_t=self._t[last:ahead],
            ahead=self._x[last:ahead],
            motion=self._motion[first:after],
        )

    def _trim(self, row: int) -> None:
        """Drop what no later stretch can hold."""
        if row:
            self._t, self._x = self._t[row:].copy(), self._x[row:].copy()
        if self._t.size:
            keep = int(np.searchsorted(self._motion_t, float(self._t[0]), side="left"))
        else:
            keep = max(0, self._motion_t.size - MOTION_KEPT_WITHOUT_EEG)
        if keep:
            self._motion_t, self._motion = self._motion_t[keep:].copy(), self._motion[keep:].copy()
