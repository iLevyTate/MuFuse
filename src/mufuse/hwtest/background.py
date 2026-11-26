"""Runs a stream supervisor on a worker thread while the guided test talks to the person.

A reconnect attempt can block for BrainFlow's whole connect timeout (15 s) while the headband is
off, so acquisition cannot share a thread with on-screen directions that must appear on time.
The worker polls, writes to disk and keeps a few measurements; the main thread only reads them.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path
from types import TracebackType

import numpy as np

from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.source import HeadbandSource
from mufuse.acquisition.supervisor import State, StreamSupervisor
from mufuse.acquisition.types import Chunk, FloatArray, StreamKind
from mufuse.hwtest.checks import Pause
from mufuse.recording.format import Gap, Marker
from mufuse.recording.writer import SessionWriter

JOIN_TIMEOUT_S = 30.0  # longer than one blocking BrainFlow connect attempt


class BackgroundAcquisition:
    def __init__(
        self,
        supervisor: StreamSupervisor,
        *,
        writer_factory: Callable[[HeadbandSource], SessionWriter] | None = None,
        poll_s: float = 0.05,
        pause_threshold_s: float = 1.0,
        keep_s: float = 30.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._sup = supervisor
        self._writer_factory = writer_factory
        self._poll_s = poll_s
        self._pause_threshold_s = pause_threshold_s
        self._keep_s = keep_s
        self._clock = clock
        self._lock = threading.RLock()
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None
        self._writer: SessionWriter | None = None
        self._counts = dict.fromkeys(StreamKind, 0)
        self._latest: dict[StreamKind, FloatArray] = {}
        self._eeg: deque[Chunk] = deque()
        self._last_eeg_at: float | None = None
        self._pauses: list[Pause] = []
        self._stopped = False
        self.error: Exception | None = None

    # --- lifecycle --------------------------------------------------------------------------

    def start(self) -> None:
        """Connect (raises SourceError) and start the worker thread."""
        self._sup.start()
        assert self._sup.source is not None
        if self._writer_factory is not None:
            self._writer = self._writer_factory(self._sup.source)
            self._sup.on_gap_closed = self._on_gap
        self._thread = threading.Thread(target=self._loop, name="mufuse-acquisition", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the worker, release the headband and finalize the session. Idempotent."""
        if self._stopped:
            return
        self._stopped = True
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(JOIN_TIMEOUT_S)
        self._sup.stop()
        with self._lock:
            if self._writer is not None:
                self._writer.finalize()

    def __enter__(self) -> BackgroundAcquisition:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.stop()

    # --- read-only views for the main thread ------------------------------------------------

    @property
    def state(self) -> State:
        return self._sup.state

    @property
    def session_dir(self) -> Path | None:
        return self._writer.session_dir if self._writer is not None else None

    def counts(self) -> dict[StreamKind, int]:
        with self._lock:
            return dict(self._counts)

    def latest(self, kind: StreamKind) -> FloatArray | None:
        with self._lock:
            return self._latest.get(kind)

    def seconds_since_data(self) -> float | None:
        with self._lock:
            last = self._last_eeg_at
        return None if last is None else self._clock() - last

    def pauses(self) -> list[Pause]:
        with self._lock:
            return list(self._pauses)

    def eeg_between(self, t0: float, t1: float) -> tuple[FloatArray, FloatArray]:
        """EEG samples whose timestamps fall in [t0, t1)."""
        with self._lock:
            chunks = list(self._eeg)
        n_channels = len(ATHENA_STREAMS[StreamKind.EEG].channel_names)
        if not chunks:
            return np.empty(0), np.empty((0, n_channels))
        ts = np.concatenate([c.timestamps for c in chunks])
        data = np.vstack([c.data for c in chunks])
        keep = (ts >= t0) & (ts < t1)
        return ts[keep], data[keep]

    def add_marker(self, marker: Marker) -> None:
        with self._lock:
            if self._writer is not None:
                self._writer.add_marker(marker)

    # --- worker -----------------------------------------------------------------------------

    def _loop(self) -> None:
        while not self._stopping.is_set():
            try:
                chunks = self._sup.poll()
                now = self._clock()
                with self._lock:
                    self._ingest(chunks, now)
                    if self._writer is not None:
                        self._writer.write(chunks)
            except Exception as exc:  # surfaced to the main thread, which fails the step
                self.error = exc
                return
            self._stopping.wait(self._poll_s)

    def _ingest(self, chunks: list[Chunk], now: float) -> None:
        for chunk in chunks:
            self._counts[chunk.kind] += chunk.n_samples
            self._latest[chunk.kind] = chunk.data[-1]
        eeg = [c for c in chunks if c.kind is StreamKind.EEG and c.n_samples]
        if not eeg:
            return
        last = self._last_eeg_at
        if last is not None and now - last > self._pause_threshold_s:
            self._pauses.append(Pause(last, now))
        self._last_eeg_at = now
        self._eeg.extend(eeg)
        newest = float(eeg[-1].timestamps[-1])
        while self._eeg and self._eeg[0].timestamps[-1] < newest - self._keep_s:
            self._eeg.popleft()

    def _on_gap(self, gap: Gap) -> None:
        with self._lock:
            if self._writer is not None:
                self._writer.add_gap(gap)
