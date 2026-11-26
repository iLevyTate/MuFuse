"""A simulated headband and a simulated person who follows the guided test's directions.

Used for `mufuse hardware-test --dry-run` and in CI. The headband can be switched off and on,
and the person's actions (blinks, jaw clench, a lifted sensor) change the simulated EEG from the
moment they happen, so the guided run's measurements and grading work end to end.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable, Collection, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import replace

import numpy as np
from rich.console import Console

from mufuse.acquisition.athena import DEFAULT_PRESET
from mufuse.acquisition.simulated import SimulatedAthena
from mufuse.acquisition.source import HeadbandSource
from mufuse.acquisition.types import (
    Chunk,
    DeviceInfo,
    FoundDevice,
    SourceError,
    StreamKind,
    StreamSpec,
)
from mufuse.hwtest.bench import Bench, DeviceDetails
from mufuse.hwtest.operator import Action, HumanOperator, KeyReader

SIM_DEVICE = FoundDevice(name="MuseS-SIM", address="00:00:00:00:00:00", rssi=-50)
SIM_INFO = {"fw": "sim-1.0", "hw": "sim", "rc": "0"}
_ARTIFACTS = frozenset({Action.BLINK, Action.CLENCH, Action.LIFT_TP9})
TP9, AF7, AF8, TP10 = 0, 1, 2, 3


class SimHeadband:
    def __init__(self, *, seed: int = 0, clock: Callable[[], float] = time.time) -> None:
        self.powered = True
        self._seed = seed
        self._clock = clock
        self._connections = 0
        self._rng = np.random.default_rng(seed)
        self._times: list[float] = []
        self._artifacts: list[Action | None] = []

    def apply(self, action: Action) -> None:
        if action is Action.POWER_OFF:
            self.powered = False
        elif action is Action.POWER_ON:
            self.powered = True
        elif action in _ARTIFACTS or action in (Action.REST, Action.RELAX):
            self._times.append(self._clock())
            self._artifacts.append(action if action in _ARTIFACTS else None)

    def source(self, preset: str, details: DeviceDetails) -> HeadbandSource:
        self._connections += 1
        inner = SimulatedAthena(
            preset=preset, seed=self._seed + self._connections, clock=self._clock
        )
        return _SimSource(self, inner, details)

    def distort(self, chunk: Chunk) -> Chunk:
        """Apply whatever the person was doing when each EEG sample was taken."""
        if chunk.kind is not StreamKind.EEG or not self._times:
            return chunk
        active = np.searchsorted(np.array(self._times), chunk.timestamps, side="right") - 1
        data = chunk.data.copy()
        for index, artifact in enumerate(self._artifacts):
            rows = np.flatnonzero(active == index)
            if artifact is None or rows.size == 0:
                continue
            if artifact is Action.CLENCH:  # muscle noise on the temporal sensors
                data[np.ix_(rows, [TP9, TP10])] += 200.0 * self._rng.standard_normal((rows.size, 2))
            elif artifact is Action.LIFT_TP9:  # sensor off the skin: no signal
                data[rows, TP9] = 0.2 * self._rng.standard_normal(rows.size)
            else:  # short blink spikes on the forehead sensors, one per second
                blink = rows[(chunk.timestamps[rows] % 1.0) < 0.04]
                data[np.ix_(blink, [AF7, AF8])] += 150.0
        return Chunk(chunk.kind, chunk.timestamps, data)


class _SimSource:
    def __init__(self, headband: SimHeadband, inner: SimulatedAthena, details: DeviceDetails):
        self._headband = headband
        self._inner = inner
        self._device = replace(
            inner.device, name=SIM_DEVICE.name, firmware=details.firmware, extra=details.extra
        )
        self._link_lost = False

    @property
    def device(self) -> DeviceInfo:
        return self._device

    @property
    def streams(self) -> Mapping[StreamKind, StreamSpec]:
        return self._inner.streams

    def start(self) -> None:
        if not self._headband.powered:
            raise SourceError("The simulated headband is switched off")
        self._inner.start()

    def read(self) -> list[Chunk]:
        if not self._headband.powered:
            self._link_lost = True  # like Bluetooth: once the headband is off, this link is gone
        if self._link_lost:
            return []
        return [self._headband.distort(c) for c in self._inner.read()]

    def stop(self) -> None:
        self._inner.stop()


class SimOperator(HumanOperator):
    """Prints the same directions as for a person, then carries them out on the simulation."""

    def __init__(
        self,
        console: Console,
        headband: SimHeadband,
        *,
        ignore: Collection[Action] = (),
        abort_at_prompt: int | None = None,
    ) -> None:
        super().__init__(console)
        self._headband = headband
        self._ignore = frozenset(ignore)
        self._abort_at_prompt = abort_at_prompt
        self._prompts = 0
        self._keys: deque[str] = deque()

    def wait_for_enter(self, prompt: str = "Press Enter to start") -> None:
        self._prompts += 1
        if self._abort_at_prompt == self._prompts:
            raise KeyboardInterrupt
        self.console.print(f"[bold]{prompt}[/bold] [dim](dry run: continuing)[/dim]")

    def act(self, action: Action) -> None:
        if action in self._ignore:
            return
        if action is Action.PRESS_SPACE:
            self._keys.append(" ")
        elif action is Action.PRESS_CTRL_C:
            raise KeyboardInterrupt
        else:
            self._headband.apply(action)

    @contextmanager
    def capture_keys(self) -> Generator[KeyReader]:
        yield self._next_key

    def _next_key(self) -> str | None:
        return self._keys.popleft() if self._keys else None


def simulated_bench(
    console: Console,
    *,
    ignore: Collection[Action] = (),
    devices: Sequence[FoundDevice] | None = None,
    abort_at_prompt: int | None = None,
    preset: str = DEFAULT_PRESET,
    seed: int = 0,
) -> Bench:
    headband = SimHeadband(seed=seed)
    found = [SIM_DEVICE] if devices is None else list(devices)
    return Bench(
        operator=SimOperator(console, headband, ignore=ignore, abort_at_prompt=abort_at_prompt),
        scan=lambda timeout: list(found),
        read_info=lambda device, timeout: dict(SIM_INFO),
        make_source=lambda device, details: headband.source(preset, details),
        remember=lambda device: None,
        saved_device=None,
        description="Simulated headband (dry run)",
        preset=preset,
        simulated=True,
    )
