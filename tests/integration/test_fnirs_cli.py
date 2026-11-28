"""The fNIRS protocol rehearsed end to end on a fake clock, and `mufuse fnirs show / score`.

A green run proves the pipeline (pre-flight, cues, markers, recording, Beer-Lambert, scorer), not
the physiology: the simulated responses are guesses (004 decision 8).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mufuse.acquisition.simulated import Rehearsal, Wearer
from mufuse.cli import (
    EXIT_BAD_ARGS,
    EXIT_UNREADABLE,
    SourceKind,
    _Attempt,  # pyright: ignore[reportPrivateUsage]
    _fnirs_protocol,  # pyright: ignore[reportPrivateUsage]
    app,
)
from mufuse.fnirs.mbll import EXPERIMENTAL
from mufuse.fnirs.protocol import FnirsScore, rehearsal_wearer, schedule
from mufuse.preflight import Preflight
from mufuse.recording.reader import load_session
from tests.conftest import QUICK, FakeClock

TICK_S = 0.5
QUICK_TIMES = {"connect_s": 0.0, "first_data_s": 0.0, "scan_s": 0.0, "stop_s": 0.0}
runner = CliRunner()


@dataclass(frozen=True)
class Ran:
    code: int
    result: FnirsScore | None
    folder: Path | None


def _protocol(out: Path, wearer: Wearer) -> Ran:
    clock = FakeClock()
    rehearsal = Rehearsal(wearer, clock=clock, sleep=clock.advance)
    code, result, folder = _fnirs_protocol(
        _Attempt("fnirs protocol", SourceKind.sim, "p1041", clock.now),
        rehearsal.source,
        rehearsal.read_key,
        out,
        clock=clock,
        sleep=lambda _: clock.advance(TICK_S),
        check=Preflight(wait_s=20.0),
        on_start=lambda: rehearsal.delay_script(rehearsal.now()),
    )
    return Ran(code, result, folder)


@pytest.fixture(scope="module")
def rehearsed(tmp_path_factory: pytest.TempPathFactory) -> Ran:
    return _protocol(tmp_path_factory.mktemp("fnirs"), replace(rehearsal_wearer(), **QUICK_TIMES))


def test_the_rehearsed_protocol_finds_every_block_in_the_expected_direction(
    rehearsed: Ran,
) -> None:
    assert rehearsed.code == 0
    assert rehearsed.result is not None
    assert len(rehearsed.result.scored) == 10
    assert rehearsed.result.share == 1.0
    assert rehearsed.result.passed


def test_the_cues_and_the_fit_check_land_in_the_recording(rehearsed: Ran) -> None:
    assert rehearsed.folder is not None
    session = load_session(rehearsed.folder)
    labels = [m.label for m in session.markers]
    assert [lab for lab in labels if lab.startswith("f:")] == [c.label for c in schedule()]
    assert labels[0] == "check:ready"
    assert session.finalized


def test_a_wearer_whose_forehead_does_nothing_does_not_pass(tmp_path: Path) -> None:
    ran = _protocol(tmp_path, replace(QUICK, **QUICK_TIMES))
    assert ran.code == 0
    assert ran.result is not None
    # Noise alone: each block's change is tiny and lands either way (its sign is not stable
    # across machines, so the share is not asserted).
    changes = [b.change_um for b in ran.result.blocks]
    assert all(c is not None and abs(c) < 0.1 for c in changes)


def test_fnirs_score_reads_the_session_back(rehearsed: Ran) -> None:
    shown = runner.invoke(app, ["fnirs", "score", str(rehearsed.folder)])
    assert shown.exit_code == 0, shown.output
    assert EXPERIMENTAL in shown.output
    assert "10 of 10 blocks (100%)" in shown.output


def test_fnirs_show_prints_each_detector_and_writes_a_csv(rehearsed: Ran, tmp_path: Path) -> None:
    out = tmp_path / "hemo.csv"
    shown = runner.invoke(
        app, ["fnirs", "show", str(rehearsed.folder), "--csv", str(out), "--short-channel"]
    )
    assert shown.exit_code == 0, shown.output
    assert EXPERIMENTAL in shown.output
    for detector in ("LI", "RI", "LO", "RO"):
        assert f"  {detector} " in shown.output
    assert "short-channel regression on (unverified geometry)" in shown.output
    header = out.read_text(encoding="utf-8").splitlines()[0]
    assert header.startswith("t,fnirs,hbo_LI")


def test_a_session_without_protocol_cues_is_refused(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["record", "--source", "sim", "--duration", "2", "--out", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    (session,) = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert runner.invoke(app, ["fnirs", "score", str(session)]).exit_code == EXIT_BAD_ARGS


def test_an_unreadable_session_exits_6(tmp_path: Path) -> None:
    assert runner.invoke(app, ["fnirs", "show", str(tmp_path / "no")]).exit_code == EXIT_UNREADABLE
    assert runner.invoke(app, ["fnirs", "score", str(tmp_path / "no")]).exit_code == EXIT_UNREADABLE


def test_the_protocol_cannot_be_replayed() -> None:
    result = runner.invoke(app, ["fnirs", "protocol", "--source", "play"])
    assert result.exit_code == EXIT_BAD_ARGS
