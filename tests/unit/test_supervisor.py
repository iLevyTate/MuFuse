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
        self.lost = 0

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

    @property
    def lost_subpackets(self) -> Mapping[StreamKind, int]:
        return {StreamKind.EEG: self.lost}


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


def test_slow_reconnect_is_not_mistaken_for_a_stall(clock: FakeClock) -> None:
    class SlowToConnect(ScriptedSource):
        def start(self) -> None:
            self._clock.advance(5.0)  # a Bluetooth scan and connect blocks for seconds

    dead = ScriptedSource(clock)
    revived = SlowToConnect(clock, alive=False)  # connected, first read has no EEG yet
    sup = StreamSupervisor(Factory([dead, revived]), clock=clock)
    sup.start()
    dead.alive = False
    _run(sup, clock, 4.2)  # stall, then the reconnect attempt that takes 5 s
    assert sup.source is revived
    _run(sup, clock, 0.1)
    assert sup.state is State.STREAMING
    assert not revived.stopped


def test_any_error_while_reconnecting_is_a_failed_attempt(clock: FakeClock) -> None:
    class Broken(ScriptedSource):
        def start(self) -> None:
            raise OSError("bluetooth adapter is off")

    dead = ScriptedSource(clock)
    factory = Factory([dead, Broken(clock), ScriptedSource(clock)])
    sup = StreamSupervisor(factory, clock=clock)
    sup.start()
    dead.alive = False
    _run(sup, clock, 4.2)  # stall, then the first attempt fails with a non-SourceError
    assert sup.state is State.RECONNECTING
    assert sup.last_error == "bluetooth adapter is off"
    _run(sup, clock, 2.1)  # the backoff goes on: next attempt 2 s later
    assert sup.state is State.STREAMING
    assert sup.last_error is None


def test_factory_error_while_reconnecting_is_a_failed_attempt(clock: FakeClock) -> None:
    dead = ScriptedSource(clock)
    calls = 0

    def factory() -> ScriptedSource:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("driver could not be loaded")
        return dead if calls == 1 else ScriptedSource(clock)

    sup = StreamSupervisor(factory, clock=clock)
    sup.start()
    dead.alive = False
    _run(sup, clock, 4.2)
    assert sup.state is State.RECONNECTING
    assert sup.last_error == "driver could not be loaded"


def test_lost_subpackets_add_up_across_reconnects(clock: FakeClock) -> None:
    first, second = ScriptedSource(clock), ScriptedSource(clock)
    sup = StreamSupervisor(Factory([first, second]), clock=clock)
    assert sup.lost_subpackets == {}
    sup.start()
    first.lost = 3
    assert sup.lost_subpackets == {StreamKind.EEG: 3}
    first.alive = False
    _run(sup, clock, 3.1)  # reconnecting: the old connection's count still stands
    assert sup.lost_subpackets == {StreamKind.EEG: 3}
    _run(sup, clock, 1.1)
    assert sup.source is second
    second.lost = 2
    assert sup.lost_subpackets == {StreamKind.EEG: 5}
