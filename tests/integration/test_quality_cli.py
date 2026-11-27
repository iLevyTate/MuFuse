"""The quality engine behind `mufuse stream` and `record` (contracts/cli.md), on the simulator."""

from __future__ import annotations

from dataclasses import replace

import pytest

from mufuse.acquisition.simulated import Rehearsal, Wearer
from mufuse.cli import (
    SourceKind,
    _Attempt,  # pyright: ignore[reportPrivateUsage]
    _run,  # pyright: ignore[reportPrivateUsage]
)
from tests.conftest import QUICK, FakeClock

TICK_S = 0.25  # the loop turns every 0.25 s in here; the same code on fewer turns


def _stream(clock: FakeClock, capsys: pytest.CaptureFixture[str], wearer: Wearer) -> list[str]:
    """The status lines of eight seconds of `mufuse stream` on a piped output."""
    rehearsal = Rehearsal(wearer, clock=clock, sleep=clock.advance)
    _run(
        _Attempt("stream", SourceKind.sim, "p1041", clock.now),
        rehearsal.source,
        8.0,
        clock=clock,
        sleep=lambda _: clock.advance(TICK_S),
        read_key=rehearsal.read_key,
    )
    return [line for line in capsys.readouterr().out.splitlines() if "coverage " in line]


def test_stream_prints_the_coverage(clock: FakeClock, capsys: pytest.CaptureFixture[str]) -> None:
    status = _stream(clock, capsys, QUICK)
    assert "coverage waiting" in status[0]  # nothing is judged before the first second
    assert "coverage full" in status[-1]


def test_stream_reads_reduced_when_both_ear_sensors_are_lifted(
    clock: FakeClock, capsys: pytest.CaptureFixture[str]
) -> None:
    wearer = replace(QUICK, lifted=((0.0, 60.0, "TP9"), (0.0, 60.0, "TP10")))
    last = _stream(clock, capsys, wearer)[-1]
    assert (
        "coverage reduced: forehead sensors good · TP9 is not connected · TP10 is not connected"
    ) in last
    assert "AF7 good" in last
    assert "AF8 good" in last
