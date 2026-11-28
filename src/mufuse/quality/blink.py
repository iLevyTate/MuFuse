"""Eye events and blinks on the forehead sensors, sample by sample (rules section 4).

A blink or a large eye movement is a slow, large swing on AF7 and AF8. The signal is band-passed
(1-10 Hz, forward only), rectified and smoothed over 32 samples; a sample is "above" when every
forehead sensor in use is above its own limit, which follows the last 30 s of that sensor. A run of
16 such samples or more is an eye event; one of at most 1.2 s is a blink.

Everything here is causal and carried from stretch to stretch, so the same samples give the same
marks and blinks whether they arrive live in small reads or are replayed from a file.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from typing import Any

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray
from scipy import signal as _scipy_signal  # pyright: ignore[reportMissingTypeStubs]

from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.types import FloatArray, StreamKind
from mufuse.quality.answer import FOREHEAD, SENSORS, Blink, Mark
from mufuse.quality.rules import RULES, Rules
from mufuse.quality.stretch import Stretch

EEG_HZ = ATHENA_STREAMS[StreamKind.EEG].sampling_rate
MAD_SCALE = 1.4826  # median absolute deviation to standard deviation, for normal data
_COLUMNS = [SENSORS.index(name) for name in FOREHEAD]  # AF7, AF8 in the EEG stream
_signal: Any = _scipy_signal  # scipy ships no type stubs; its two results are typed below


class Envelope:
    """Band-passed, rectified and smoothed, one column per sensor; zero state at the anchor."""

    def __init__(self, columns: int = 2, rules: Rules = RULES) -> None:
        self._sos: FloatArray = np.asarray(
            _signal.butter(2, list(rules.eye_band_hz), btype="bandpass", fs=EEG_HZ, output="sos"),
            dtype=np.float64,
        )
        self._n = rules.envelope_n
        self._zi: FloatArray = np.zeros((self._sos.shape[0], 2, columns))
        self._tail: FloatArray = np.zeros((self._n - 1, columns))  # before the anchor: 0

    def step(self, x: FloatArray, *, keep: bool = True) -> FloatArray:
        """The envelope of the samples `x` (n, columns) that follow the ones already seen.
        With `keep=False` it only looks: the next call starts where this one started."""
        filtered, zi = _signal.sosfilt(self._sos, x, axis=0, zi=self._zi)
        rectified = np.vstack([self._tail, np.abs(np.asarray(filtered, dtype=np.float64))])
        envelope = sliding_window_view(rectified, self._n, axis=0).mean(axis=-1)
        if keep:
            self._zi = np.asarray(zi, dtype=np.float64)
            self._tail = rectified[rectified.shape[0] - (self._n - 1) :]
        return np.asarray(envelope, dtype=np.float64)


def limit(values: FloatArray, rules: Rules = RULES) -> float:
    """Median + 4 robust spreads of one sensor's recent envelope, and never under the floor."""
    if values.size == 0:
        return rules.eye_floor_uv
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    return max(median + rules.eye_mad_factor * MAD_SCALE * mad, rules.eye_floor_uv)


def _runs(above: NDArray[np.bool_]) -> list[tuple[int, int]]:
    """Every row of `True` in `above`, as (first, last) indices."""
    edges = np.diff(np.concatenate([[0], above.astype(np.int8), [0]]))
    firsts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    return [(int(f), int(e) - 1) for f, e in zip(firsts, ends, strict=True)]


def eye_events(above: NDArray[np.bool_], rules: Rules = RULES) -> list[tuple[int, int]]:
    """The runs of `above` that are eye events: 16 samples or more."""
    return [(f, last) for f, last in _runs(above) if last - f + 1 >= rules.eye_min_n]


def _forehead(eeg: FloatArray) -> FloatArray:
    """AF7 and AF8, with a missing sample replaced by the mean of its sensor's stretch."""
    x = np.array(eeg[:, _COLUMNS], dtype=np.float64)
    for c in range(x.shape[1]):
        finite = np.isfinite(x[:, c])
        if not finite.all():
            x[~finite, c] = float(np.mean(x[finite, c])) if finite.any() else 0.0
    return x


class _Run:
    """A row of above samples that reaches the newest judged sample."""

    def __init__(self, first: int, t: float, reportable: bool) -> None:
        self.first, self.t, self.reportable = first, t, reportable


class EyeDetector:
    """The eye mark of each stretch, and the blinks that end in it."""

    def __init__(self, rules: Rules = RULES) -> None:
        self._rules = rules
        self._last_blink: float | None = None
        self._anchor()

    def _anchor(self) -> None:
        rules = self._rules
        self._envelope = Envelope(len(_COLUMNS), rules)
        self._n = 0  # samples since the anchor
        kept = round(rules.limit_s * EEG_HZ) // rules.limit_every_n
        self._history: deque[FloatArray] = deque(maxlen=kept)  # every 8th envelope sample
        self._limits: FloatArray | None = None  # for the next stretch
        self._open: _Run | None = None
        self._events: list[tuple[int, int]] = []  # closed eye events that may still mark

    def judge(self, stretch: Stretch, in_use: Sequence[bool]) -> tuple[Mark, tuple[Blink, ...]]:
        """`in_use`: AF7 and AF8 are in use in this stretch (their contact is not `none`)."""
        rules, i = self._rules, self._n
        used = np.array(in_use, dtype=bool)
        now = self._limits if self._limits is not None else self._limits_now()
        envelope = self._envelope.step(_forehead(stretch.eeg))
        rows: NDArray[np.int_] = np.arange(i, i + int(envelope.shape[0]))
        self._history.extend(envelope[rows % rules.limit_every_n == 0])
        self._limits = self._limits_now()
        self._n += envelope.shape[0]
        above = _above(envelope, now, used)
        ahead = np.zeros(0, dtype=bool)
        if stretch.ahead.shape[0]:
            look = self._envelope.step(_forehead(stretch.ahead), keep=False)
            ahead = _above(look, self._limits, used)  # those samples lie in the next stretch

        warm = stretch.index // rules.stretch_n >= rules.eye_warmup  # index counts samples
        available = warm and bool(used.any())
        closed, still_open = self._close_runs(above, stretch, reportable=available)
        events = [(first, last) for first, last, _ in closed if last - first + 1 >= rules.eye_min_n]
        if not available:
            mark: Mark = "unavailable"
        else:
            mark = "yes" if self._marked(i, events, still_open, ahead) else "no"
        # Kept while they can still reach the next stretch's window, which opens 32 samples early.
        self._events = [e for e in self._events + events if e[1] >= self._n - rules.eye_margin_n]
        self._open = still_open
        return mark, self._blinks(closed)

    def close(self) -> tuple[Blink, ...]:
        """The newest sample before a gap, or the last one: the open run ends. Then a new anchor."""
        found: tuple[Blink, ...] = ()
        if self._open is not None:
            found = self._blinks([(self._open.first, self._n - 1, self._open)])
        self._anchor()
        return found

    def _limits_now(self) -> FloatArray:
        if not self._history:
            return np.full(len(_COLUMNS), self._rules.eye_floor_uv)
        recent = np.vstack(self._history)
        return np.array([limit(recent[:, c], self._rules) for c in range(recent.shape[1])])

    def _close_runs(
        self, above: NDArray[np.bool_], stretch: Stretch, *, reportable: bool
    ) -> tuple[list[tuple[int, int, _Run]], _Run | None]:
        """The runs that ended in this stretch, and the one that reaches its last sample."""
        i, closed, still_open = self._n - above.size, list[tuple[int, int, _Run]](), None
        runs = _runs(above)
        if self._open is not None and (not runs or runs[0][0] != 0):
            closed.append((self._open.first, i - 1, self._open))  # it ended before this stretch
        for first, last in runs:
            if first == 0 and self._open is not None:
                run = self._open
            else:
                run = _Run(i + first, float(stretch.t[first]), reportable)
            if last == above.size - 1:
                still_open = run
            else:
                closed.append((run.first, i + last, run))
        return closed, still_open

    def _marked(
        self,
        i: int,
        events: list[tuple[int, int]],
        still_open: _Run | None,
        ahead: NDArray[np.bool_],
    ) -> bool:
        rules = self._rules
        if any(last >= i - rules.eye_margin_n for _, last in self._events) or events:
            return True
        end = i + rules.stretch_n - 1  # the stretch's last sample
        runs = _runs(ahead)
        if still_open is not None:
            carried = runs[0][1] + 1 if runs and runs[0][0] == 0 else 0
            if end - still_open.first + 1 + carried >= rules.eye_min_n:
                return True
            runs = runs[1:] if carried else runs
        reach = rules.eye_margin_n - 1  # i + 287 is the 32nd sample after the stretch
        return any(f <= reach and last - f + 1 >= rules.eye_min_n for f, last in runs)

    def _blinks(self, closed: Sequence[tuple[int, int, _Run]]) -> tuple[Blink, ...]:
        rules, found = self._rules, list[Blink]()
        for first, last, run in closed:
            n = last - first + 1
            if not (rules.eye_min_n <= n <= rules.blink_max_n) or not run.reportable:
                continue
            if self._last_blink is not None and run.t - self._last_blink < rules.blink_apart_s:
                continue
            self._last_blink = run.t
            found.append(Blink(run.t, n / EEG_HZ))
        return tuple(found)


def _above(envelope: FloatArray, limits: FloatArray, used: NDArray[np.bool_]) -> NDArray[np.bool_]:
    """Every sensor in use is above its limit; with none in use, nothing is above."""
    if not used.any():
        return np.zeros(envelope.shape[0], dtype=bool)
    return np.all(envelope[:, used] > limits[used], axis=1)
