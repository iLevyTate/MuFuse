"""Keeps a headband stream alive: detects stalls, reconnects with backoff, records gaps.

Pure logic driven by `poll()` and an injectable clock, so it is fully testable without hardware.
Gaps are recorded, never interpolated (constitution IV).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from enum import Enum

from mufuse.acquisition.source import HeadbandSource
from mufuse.acquisition.types import Chunk, SourceError, StreamKind
from mufuse.recording.format import Gap, GapReason, ReconnectStep, ReconnectWhat


class State(Enum):
    STREAMING = "streaming"
    RECONNECTING = "reconnecting"
    STOPPED = "stopped"


class StreamSupervisor:
    def __init__(
        self,
        source_factory: Callable[[], HeadbandSource],
        *,
        clock: Callable[[], float] = time.time,
        stall_after: float = 3.0,
        first_data_after: float = 8.0,
        backoff: Sequence[float] = (1.0, 2.0, 4.0, 8.0),
    ) -> None:
        self._factory = source_factory
        self._clock = clock
        self._stall_after = stall_after
        # A new connection may take longer to send its first sample than a running one takes
        # between two; held to `stall_after` it would be torn down and replaced over and over.
        self._first_data_after = first_data_after
        self._backoff = tuple(backoff)
        self.state = State.STOPPED
        self.source: HeadbandSource | None = None
        self.gaps: list[Gap] = []
        self.open_gap: Gap | None = None
        self.on_gap_closed: Callable[[Gap], None] | None = None
        # Told each step of a reconnect as it happens, so a slow one shows where the time went.
        self.on_reconnect_step: Callable[[ReconnectStep], None] | None = None
        self.last_error: str | None = None  # why the latest reconnect attempt failed
        self._lost_before: dict[StreamKind, int] = {}  # from connections already replaced
        self._last_data_at = 0.0
        self._awaiting_first = False  # connected, no EEG sample from this connection yet
        self._last_sample_t: float | None = None
        self._attempt = 0
        self._next_attempt_at = 0.0

    def start(self) -> None:
        """Initial connection; raises SourceError so the caller can report it to the user."""
        source = self._factory()
        source.start()
        self.source = source
        self.state = State.STREAMING
        self._last_data_at = self._clock()
        self._awaiting_first = True

    def stop(self) -> None:
        if self.source is not None:
            self.source.stop()
        self.state = State.STOPPED

    @property
    def lost_subpackets(self) -> dict[StreamKind, int]:
        """Subpackets lost on the headset link, summed over every connection of this run."""
        total = dict(self._lost_before)
        if self.source is not None:
            for kind, lost in self.source.lost_subpackets.items():
                total[kind] = total.get(kind, 0) + lost
        return total

    def poll(self) -> list[Chunk]:
        now = self._clock()
        if self.state is State.STREAMING:
            return self._poll_streaming(now)
        if self.state is State.RECONNECTING and now >= self._next_attempt_at:
            self._try_reconnect(now)
        return []

    def _poll_streaming(self, now: float) -> list[Chunk]:
        assert self.source is not None
        try:
            chunks = self.source.read()
        except SourceError:
            self._begin_reconnect(now, "disconnect")
            return []
        eeg = [c for c in chunks if c.kind is StreamKind.EEG and c.n_samples]
        if eeg:
            if self.open_gap is not None:
                self._close_gap(float(eeg[0].timestamps[0]))
                self._step(now, "first_sample")
            self._last_data_at = now
            self._awaiting_first = False
            self._last_sample_t = float(eeg[-1].timestamps[-1])
        else:
            allowed = self._first_data_after if self._awaiting_first else self._stall_after
            if now - self._last_data_at > allowed:
                self._begin_reconnect(now, "stall")
        return chunks

    def _begin_reconnect(self, now: float, reason: GapReason) -> None:
        if self.open_gap is None:  # else a reconnect sent nothing: the gap it is in goes on
            start = self._last_sample_t if self._last_sample_t is not None else self._last_data_at
            self.open_gap = Gap(stream="all", start=start, end=None, reason=reason)
        self._step(now, "lost", reason)
        if self.source is not None:
            self.source.stop()
        self._step(self._clock(), "released")
        self.state = State.RECONNECTING
        self._attempt = 0
        self._next_attempt_at = now + self._backoff[0]

    def _try_reconnect(self, now: float) -> None:
        self._step(now, "attempt")
        try:
            source = self._factory()
            source.start()
        except Exception as exc:  # whatever went wrong, it is a failed attempt: keep trying
            self.last_error = str(exc)
            self._step(self._clock(), "failed", self.last_error)
            self._attempt += 1
            # Counted from the attempt's start: after a long failed scan the next one starts at
            # once, while quick failures still wait out the backoff.
            self._next_attempt_at = now + self._backoff[min(self._attempt, len(self._backoff) - 1)]
            return
        self._lost_before = self.lost_subpackets
        self.source = source
        self.state = State.STREAMING
        self.last_error = None
        self._last_data_at = self._clock()  # connecting can take seconds; `now` is stale
        self._awaiting_first = True
        self._step(self._last_data_at, "connected")

    def _close_gap(self, end: float) -> None:
        assert self.open_gap is not None
        gap = Gap(self.open_gap.stream, self.open_gap.start, end, self.open_gap.reason)
        self.gaps.append(gap)
        self.open_gap = None
        if self.on_gap_closed is not None:
            self.on_gap_closed(gap)

    def _step(self, t: float, what: ReconnectWhat, detail: str | None = None) -> None:
        if self.on_reconnect_step is not None:
            self.on_reconnect_step(ReconnectStep(t, what, detail))
