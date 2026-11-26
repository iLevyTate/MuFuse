from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pytest

from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.supervisor import State, StreamSupervisor
from mufuse.acquisition.types import Chunk, DeviceInfo, SourceError, StreamKind, StreamSpec
from tests.conftest import FakeClock


class ScriptedSource:
    """Emits one EEG sample per read while `alive`; can be told to fail on start."""

    def __init__(self, clock: FakeClock, *, alive: bool = True, fail_start: bool = False) -> None:
        self._clock = clock
        self.alive = alive
        self.fail_start = fail_start
        self.stopped = False

    @property
    def device(self) -> DeviceInfo:
        return DeviceInfo(name="scripted", preset="p1041", driver="test")

    @property
    def streams(self) -> Mapping[StreamKind, StreamSpec]:
        return ATHENA_STREAMS

    def start(self) -> None:
        if self.fail_start:
            raise SourceError("no device")

    def read(self) -> list[Chunk]:
        if not self.alive:
            return []
        return [Chunk(StreamKind.EEG, np.array([self._clock()]), np.zeros((1, 8)))]

    def stop(self) -> None:
        self.stopped = True


class Factory:
    def __init__(self, sources: list[ScriptedSource]) -> None:
        self.sources = sources
        self.calls = 0

    def __call__(self) -> ScriptedSource:
        src = self.sources[min(self.calls, len(self.sources) - 1)]
        self.calls += 1
        return src


def _run(sup: StreamSupervisor, clock: FakeClock, seconds: float, step: float = 0.05) -> None:
    for _ in range(round(seconds / step)):
        clock.advance(step)
        sup.poll()


def test_streams_normally(clock: FakeClock) -> None:
    sup = StreamSupervisor(Factory([ScriptedSource(clock)]), clock=clock)
    sup.start()
    _run(sup, clock, 1.0)
    assert sup.state is State.STREAMING
    assert sup.gaps == []


def test_stall_detected_after_three_seconds(clock: FakeClock) -> None:
    src = ScriptedSource(clock)
    sup = StreamSupervisor(Factory([src]), clock=clock)
    sup.start()
    _run(sup, clock, 1.0)
    src.alive = False
    _run(sup, clock, 2.9)
    assert sup.state is State.STREAMING
    _run(sup, clock, 0.2)
    assert sup.state is State.RECONNECTING
    assert src.stopped
    assert sup.open_gap is not None


def test_reconnect_closes_gap_at_first_new_sample(clock: FakeClock) -> None:
    dead = ScriptedSource(clock)
    revived = ScriptedSource(clock)
    sup = StreamSupervisor(Factory([dead, revived]), clock=clock)
    sup.start()
    _run(sup, clock, 1.0)
    last_good = clock.now
    dead.alive = False
    _run(sup, clock, 3.1)  # stall -> reconnecting; first attempt due 1 s later
    _run(sup, clock, 1.1)
    assert sup.state is State.STREAMING
    (gap,) = sup.gaps
    assert gap.start == pytest.approx(last_good)
    assert gap.end is not None
    assert gap.end > gap.start
    assert gap.reason == "stall"


def test_backoff_schedule(clock: FakeClock) -> None:
    failing = ScriptedSource(clock, fail_start=True)
    factory = Factory([ScriptedSource(clock), failing])
    sup = StreamSupervisor(factory, clock=clock, backoff=(1.0, 2.0, 4.0))
    sup.start()
    factory.sources[0].alive = False
    _run(sup, clock, 3.05)  # stalled
    calls_at_stall = factory.calls
    _run(sup, clock, 1.0)  # attempt 1 at +1 s
    _run(sup, clock, 2.0)  # attempt 2 at +2 s
    _run(sup, clock, 4.0)  # attempt 3 at +4 s
    _run(sup, clock, 3.9)  # still waiting (next at +4 s, capped)
    assert factory.calls - calls_at_stall == 3
    assert sup.state is State.RECONNECTING


def test_read_error_triggers_immediate_reconnect(clock: FakeClock) -> None:
    class Exploding(ScriptedSource):
        def read(self) -> list[Chunk]:
            raise SourceError("device lost")

    sup = StreamSupervisor(Factory([Exploding(clock), ScriptedSource(clock)]), clock=clock)
    sup.start()
    sup.poll()
    assert sup.state is State.RECONNECTING
    assert sup.open_gap is not None
    assert sup.open_gap.reason == "disconnect"


def test_initial_connect_failure_raises(clock: FakeClock) -> None:
    sup = StreamSupervisor(Factory([ScriptedSource(clock, fail_start=True)]), clock=clock)
    with pytest.raises(SourceError):
        sup.start()
