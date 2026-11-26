"""The single interface every headband source implements (real, simulated, playback)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from mufuse.acquisition.types import Chunk, DeviceInfo, StreamKind, StreamSpec


class HeadbandSource(Protocol):
    @property
    def device(self) -> DeviceInfo: ...

    @property
    def streams(self) -> Mapping[StreamKind, StreamSpec]: ...

    def start(self) -> None:
        """Connect and begin streaming. Raises SourceError on failure."""
        ...

    def read(self) -> list[Chunk]:
        """Non-blocking: every sample received since the previous call (empty chunks omitted)."""
        ...

    def stop(self) -> None:
        """Release the device. Idempotent and safe after errors."""
        ...
