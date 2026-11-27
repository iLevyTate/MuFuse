"""Replays a recorded session through the HeadbandSource interface."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from pathlib import Path

import numpy as np

from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.types import Chunk, DeviceInfo, SourceError, StreamKind, StreamSpec
from mufuse.recording.reader import LoadedSession, load_session


class PlaybackSource:
    """Emits recorded samples in original timing (``realtime=True``) or all at once."""

    def __init__(
        self, path: Path, *, realtime: bool = True, clock: Callable[[], float] = time.time
    ) -> None:
        self._session: LoadedSession = load_session(path)
        self._realtime = realtime
        self._clock = clock
        self._t0: float | None = None
        self._cursor: dict[StreamKind, int] = {}
        dev = self._session.manifest["device"]
        self._device = DeviceInfo(
            name=dev["name"], preset=dev["preset"], driver="playback", address=dev.get("address")
        )

    @property
    def device(self) -> DeviceInfo:
        return self._device

    @property
    def streams(self) -> Mapping[StreamKind, StreamSpec]:
        return ATHENA_STREAMS

    @property
    def lost_subpackets(self) -> Mapping[StreamKind, int]:
        return dict.fromkeys(ATHENA_STREAMS, 0)  # no headset link, so nothing is lost on it

    @property
    def exhausted(self) -> bool:
        return all(
            self._cursor.get(k, 0) >= ts.size for k, (ts, _) in self._session.streams.items()
        )

    def start(self) -> None:
        self._t0 = self._clock()
        self._cursor = dict.fromkeys(self._session.streams, 0)

    def stop(self) -> None:
        self._t0 = None

    def read(self) -> list[Chunk]:
        if self._t0 is None:
            raise SourceError("PlaybackSource.read() called before start()")
        started_at = float(self._session.manifest["started_at"])
        horizon = started_at + (self._clock() - self._t0) if self._realtime else np.inf
        chunks: list[Chunk] = []
        for kind, (ts, data) in self._session.streams.items():
            lo = self._cursor[kind]
            hi = int(np.searchsorted(ts, horizon, side="right")) if self._realtime else ts.size
            if hi > lo:
                chunks.append(Chunk(kind, ts[lo:hi], data[lo:hi]))
                self._cursor[kind] = hi
        return chunks
