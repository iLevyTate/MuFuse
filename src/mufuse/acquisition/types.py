"""Core acquisition value types shared by every headband source."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


class StreamKind(StrEnum):
    EEG = "eeg"
    MOTION = "motion"
    OPTICS = "optics"


@dataclass(frozen=True)
class StreamSpec:
    kind: StreamKind
    channel_names: tuple[str, ...]
    sampling_rate: float
    units: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.sampling_rate <= 0:
            raise ValueError("sampling_rate must be positive")
        if len(self.units) != len(self.channel_names):
            raise ValueError("units must have one entry per channel")


@dataclass(frozen=True)
class Chunk:
    """Samples from one stream: timestamps (n,) on the session clock and data (n, channels)."""

    kind: StreamKind
    timestamps: FloatArray
    data: FloatArray

    def __post_init__(self) -> None:
        if self.data.ndim != 2:
            raise ValueError("data must be 2-D (samples, channels)")
        if self.timestamps.shape[0] != self.data.shape[0]:
            raise ValueError("timestamps and data must have the same number of samples")
        if self.timestamps.size > 1 and not bool(np.all(np.diff(self.timestamps) > 0)):
            raise ValueError("timestamps must be strictly increasing")

    @property
    def n_samples(self) -> int:
        return int(self.timestamps.shape[0])


@dataclass(frozen=True)
class DeviceInfo:
    name: str
    preset: str
    driver: str
    address: str | None = None
    firmware: str | None = None
    extra: dict[str, str] = field(default_factory=dict[str, str])


@dataclass(frozen=True)
class FoundDevice:
    """A headband seen in a Bluetooth scan."""

    name: str
    address: str
    rssi: int


class SourceError(RuntimeError):
    """Raised when a source cannot connect or loses the device unrecoverably."""
