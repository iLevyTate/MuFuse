"""The quality engine behind `mufuse stream` and `record` (contracts/cli.md), on the simulator."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.simulated import Rehearsal, Wearer
from mufuse.acquisition.types import DeviceInfo
from mufuse.cli import (
    EXIT_UNREADABLE,
    SourceKind,
    _Attempt,  # pyright: ignore[reportPrivateUsage]
    _run,  # pyright: ignore[reportPrivateUsage]
    app,
)
from mufuse.recording.writer import SessionWriter
from tests.conftest import QUICK, FakeClock, rehearse

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


# mufuse inspect ---------------------------------------------------------------------------


def _recorded(tmp_path: Path, clock: FakeClock, wearer: Wearer, *, finalize: bool = True) -> Path:
    writer = SessionWriter.create(
        tmp_path, DeviceInfo("SimulatedAthena", "p1041", "simulated"), ATHENA_STREAMS, clock=clock
    )
    for read in rehearse(wearer, clock, 12.0):
        writer.write(read)
    if finalize:
        writer.finalize()
    else:
        writer.close_files()  # as a crash leaves it
    return writer.session_dir


def _hashes(folder: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}


def test_inspect_ends_with_the_quality_summary(tmp_path: Path, clock: FakeClock) -> None:
    session = _recorded(tmp_path, clock, replace(QUICK, lifted=((0.0, 60.0, "TP9"),)))
    before = _hashes(session)
    shown = CliRunner().invoke(app, ["inspect", str(session)])
    assert shown.exit_code == 0, shown.output
    block = shown.output[shown.output.index("Signal quality (rules 1)") :].splitlines()
    assert block[1].startswith("  judged 0:12 · no data 0:00")
    assert block[2] == "  sensor   good  settling  noisy  no contact  clean"
    assert block[3].startswith("  TP9        0%        0%     0%        100%")
    assert block[7].startswith("  coverage  full 0% · reduced ")
    assert block[8].startswith("  blinks    0 (0.0 per minute over ")
    assert _hashes(session) == before  # inspecting changes nothing


def test_inspect_judges_an_interrupted_session(tmp_path: Path, clock: FakeClock) -> None:
    session = _recorded(tmp_path, clock, QUICK, finalize=False)
    shown = CliRunner().invoke(app, ["inspect", str(session)])
    assert shown.exit_code == 0, shown.output
    assert "NOT finalized" in shown.output
    assert "Signal quality (rules 1)" in shown.output


def test_inspect_of_a_session_without_samples_says_not_available(
    tmp_path: Path, clock: FakeClock
) -> None:
    writer = SessionWriter.create(
        tmp_path, DeviceInfo("MuseS-TEST", "p1041", "simulated"), ATHENA_STREAMS, clock=clock
    )
    writer.finalize()
    shown = CliRunner().invoke(app, ["inspect", str(writer.session_dir)])
    assert shown.exit_code == 0, shown.output
    assert "judged 0:00" in shown.output
    assert "not available" in shown.output


def test_inspect_keeps_its_exit_code_for_an_unreadable_session(tmp_path: Path) -> None:
    shown = CliRunner().invoke(app, ["inspect", str(tmp_path / "missing")])
    assert shown.exit_code == EXIT_UNREADABLE
