"""Deterministic Athena-shaped synthetic source for development and CI (no hardware)."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence

import numpy as np

from mufuse.acquisition.athena import ATHENA_STREAMS, DEFAULT_PRESET, validate_preset
from mufuse.acquisition.types import (
    Chunk,
    DeviceInfo,
    FloatArray,
    SourceError,
    StreamKind,
    StreamSpec,
)

Clock = Callable[[], float]


class SimulatedAthena:
    """Generates plausible signals sample-accurately from a (possibly fake) clock.

    EEG: 10 Hz alpha + broadband noise (µV). Motion: gravity on Z + noise. Optics: DC + 1.2 Hz
    pulse. ``dropouts`` are (start, end) windows in seconds after ``start()`` with no samples,
    used to exercise stall handling.
    """

    def __init__(
        self,
        *,
        clock: Clock = time.time,
        seed: int = 0,
        preset: str = DEFAULT_PRESET,
        dropouts: Sequence[tuple[float, float]] = (),
    ) -> None:
        self._clock = clock
        self._seed = seed
        self._dropouts = tuple(dropouts)
        self._device = DeviceInfo(
            name="SimulatedAthena", preset=validate_preset(preset), driver="simulated"
        )
        self._t0: float | None = None
        self._emitted: dict[StreamKind, int] = {}
        self._rngs: dict[StreamKind, np.random.Generator] = {}

    @property
    def device(self) -> DeviceInfo:
        return self._device

    @property
    def streams(self) -> Mapping[StreamKind, StreamSpec]:
        return ATHENA_STREAMS

    def start(self) -> None:
        self._t0 = self._clock()
        self._emitted = dict.fromkeys(StreamKind, 0)
        self._rngs = {k: np.random.default_rng([self._seed, i]) for i, k in enumerate(StreamKind)}

    def stop(self) -> None:
        self._t0 = None

    def read(self) -> list[Chunk]:
        if self._t0 is None:
            raise SourceError("SimulatedAthena.read() called before start()")
        elapsed = self._clock() - self._t0
        chunks: list[Chunk] = []
        for kind, spec in ATHENA_STREAMS.items():
            # UNIX-epoch floats resolve only ~0.24 µs, so allow 1/1000 sample of rounding slack.
            due = int(elapsed * spec.sampling_rate + 1e-3)
            idx = np.arange(self._emitted[kind], due)
            self._emitted[kind] = due
            rel = idx / spec.sampling_rate
            # Signals are generated for every index so the RNG stays aligned, then masked.
            data = self._generate(kind, spec, rel)
            keep = ~self._in_dropout(rel)
            if keep.any():
                chunks.append(Chunk(kind, self._t0 + rel[keep], data[keep]))
        return chunks

    def _in_dropout(self, rel: FloatArray) -> np.ndarray:
        mask = np.zeros(rel.shape, dtype=bool)
        for start, end in self._dropouts:
            mask |= (rel >= start) & (rel < end)
        return mask

    def _generate(self, kind: StreamKind, spec: StreamSpec, rel: FloatArray) -> FloatArray:
        rng = self._rngs[kind]
        n, c = rel.size, len(spec.channel_names)
        noise = rng.standard_normal((n, c))
        if kind is StreamKind.EEG:
            alpha = 20.0 * np.sin(2 * np.pi * 10.0 * rel)[:, None]
            return alpha + 8.0 * noise
        if kind is StreamKind.MOTION:
            gravity = np.zeros((n, c))
            gravity[:, 2] = 1.0
            return gravity + 0.01 * noise
        pulse = np.sin(2 * np.pi * 1.2 * rel)[:, None]
        optics = 20_000.0 + 150.0 * pulse + 5.0 * noise
        optics[:, -1] = 100.0 - rel / 600.0  # battery percent, slowly draining
        return optics
