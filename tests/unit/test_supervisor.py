from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pytest

from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.supervisor import State, StreamSupervisor
from mufuse.acquisition.types import Chunk, DeviceInfo, SourceError, StreamKind, StreamSpec
from mufuse.recording.format import ReconnectStep
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
    sup.poll()  # the first sample: from here on the usual 3 s apply
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
    sup.poll()
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
    sup.poll()
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
    sup.poll()
    dead.alive = False
    _run(sup, clock, 4.2)
    assert sup.state is State.RECONNECTING
    assert sup.last_error == "driver could not be loaded"


def test_lost_subpackets_add_up_across_reconnects(clock: FakeClock) -> None:
    first, second = ScriptedSource(clock), ScriptedSource(clock)
    sup = StreamSupervisor(Factory([first, second]), clock=clock)
    assert sup.lost_subpackets == {}
    sup.start()
    sup.poll()
    first.lost = 3
    assert sup.lost_subpackets == {StreamKind.EEG: 3}
    first.alive = False
    _run(sup, clock, 3.1)  # reconnecting: the old connection's count still stands
    assert sup.lost_subpackets == {StreamKind.EEG: 3}
    _run(sup, clock, 1.1)
    assert sup.source is second
    second.lost = 2
    assert sup.lost_subpackets == {StreamKind.EEG: 5}


def test_every_step_of_a_reconnect_is_reported_with_its_time(clock: FakeClock) -> None:
    class Gone(ScriptedSource):
        def start(self) -> None:
            self._clock.advance(16.0)  # a scan that finds nothing
            raise SourceError("no device")

    class SlowToConnect(ScriptedSource):
        def start(self) -> None:
            self._clock.advance(5.0)

    class SlowToLetGo(ScriptedSource):
        def stop(self) -> None:
            self._clock.advance(2.0)

    dead = SlowToLetGo(clock)
    sup = StreamSupervisor(Factory([dead, Gone(clock), SlowToConnect(clock)]), clock=clock)
    steps: list[ReconnectStep] = []
    sup.on_reconnect_step = steps.append
    sup.start()
    t0 = clock.now
    _run(sup, clock, 1.0)
    assert steps == []
    dead.alive = False
    _run(sup, clock, 6.0)
    assert sup.state is State.STREAMING
    assert [(s.what, s.detail) for s in steps] == [
        ("lost", "stall"),
        ("released", None),
        ("attempt", None),
        ("failed", "no device"),
        ("attempt", None),
        ("connected", None),
        ("first_sample", None),
    ]
    lost, released, first, failed, second, connected, sample = (s.t - t0 for s in steps)
    assert lost == pytest.approx(4.05, abs=0.06)  # 3 s without a sample
    assert released == pytest.approx(lost + 2.0)
    assert first == pytest.approx(released + 0.05)  # the backoff ran out during the release
    assert failed == pytest.approx(first + 16.0)
    assert second == pytest.approx(failed + 0.05)
    assert connected == pytest.approx(second + 5.0)
    assert sample == pytest.approx(connected + 0.05)


def test_a_new_connection_gets_longer_for_its_first_sample(clock: FakeClock) -> None:
    src = ScriptedSource(clock, alive=False)  # connected, but the first sample takes a while
    sup = StreamSupervisor(Factory([src]), clock=clock)
    sup.start()
    _run(sup, clock, 5.0)
    assert sup.state is State.STREAMING
    assert not src.stopped
    src.alive = True
    _run(sup, clock, 1.0)
    src.alive = False
    _run(sup, clock, 3.1)  # once it has streamed, the usual 3 s apply again
    assert sup.state is State.RECONNECTING


def test_a_new_connection_that_never_sends_is_replaced(clock: FakeClock) -> None:
    silent = ScriptedSource(clock, alive=False)
    sup = StreamSupervisor(Factory([silent, ScriptedSource(clock)]), clock=clock)
    sup.start()
    _run(sup, clock, 7.9)
    assert sup.state is State.STREAMING
    _run(sup, clock, 0.2)
    assert sup.state is State.RECONNECTING
    assert silent.stopped
    assert sup.open_gap is not None
    assert sup.open_gap.reason == "stall"


def test_a_reconnect_that_never_sends_is_replaced_too(clock: FakeClock) -> None:
    dead = ScriptedSource(clock)
    silent = ScriptedSource(clock, alive=False)
    sup = StreamSupervisor(Factory([dead, silent, ScriptedSource(clock)]), clock=clock)
    sup.start()
    _run(sup, clock, 1.0)
    dead.alive = False
    _run(sup, clock, 4.2)  # stall, then the attempt that connects without data
    assert sup.source is silent
    _run(sup, clock, 7.7)
    assert not silent.stopped
    _run(sup, clock, 1.5)  # given up on after 8 s; the next attempt comes 1 s later
    assert silent.stopped
    assert sup.state is State.STREAMING
    assert len(sup.gaps) == 1  # one gap from the first loss to the first sample after it
