"""`mufuse breathe` rehearsed on a fake clock, and `mufuse exercise` (009)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mufuse.acquisition.simulated import Rehearsal
from mufuse.cli import (
    EXIT_BAD_ARGS,
    SourceKind,
    _Attempt,  # pyright: ignore[reportPrivateUsage]
    _breathe,  # pyright: ignore[reportPrivateUsage]
    _play,  # pyright: ignore[reportPrivateUsage]
    app,
)
from mufuse.exercises.breathe import breathe_guide, rehearsal_wearer
from mufuse.exercises.library import load
from mufuse.preflight import Preflight
from mufuse.recording.reader import load_session
from tests.conftest import FakeClock

QUICK = {"connect_s": 0.0, "first_data_s": 0.0, "scan_s": 0.0, "stop_s": 0.0}
TICK_S = 0.5


def test_a_rehearsed_session_shows_the_bigger_swing_while_pacing(
    tmp_path: Path, clock: FakeClock
) -> None:
    rate, minutes = 6.0, 2.0
    rehearsal = Rehearsal(
        replace(rehearsal_wearer(rate, minutes), **QUICK), clock=clock, sleep=clock.advance
    )
    code, report, folder = _breathe(
        _Attempt("breathe", SourceKind.sim, "p1041", clock.now),
        rehearsal.source,
        rehearsal.read_key,
        tmp_path,
        breathe_guide(rate, minutes),
        rate,
        clock=clock,
        sleep=lambda _: clock.advance(TICK_S),
        check=Preflight(wait_s=20.0),
        on_start=lambda: rehearsal.delay_script(rehearsal.now()),
    )
    assert code == 0
    assert report is not None
    before, pace = report.phases["before"], report.phases["pace"]
    assert before.swing_ms is not None
    assert pace.swing_ms is not None
    assert pace.swing_ms > 1.5 * before.swing_ms
    assert report.raised("swing_ms") is True
    assert pace.hr_bpm == pytest.approx(72.0, abs=3.0)
    assert folder is not None
    labels = [m.label for m in load_session(folder).markers]
    assert [x for x in labels if x.startswith("b:")] == ["b:before", "b:pace", "b:after", "b:end"]


def test_seconds_the_head_moved_are_left_out_of_the_pacing_phase(
    tmp_path: Path, clock: FakeClock
) -> None:
    rate, minutes = 6.0, 2.0
    turns = ((150.0, 156.0), (200.0, 204.0))  # both inside the pacing phase (120-240 s)
    wearer = replace(rehearsal_wearer(rate, minutes), turns=turns, **QUICK)
    rehearsal = Rehearsal(wearer, clock=clock, sleep=clock.advance)
    code, report, _ = _breathe(
        _Attempt("breathe", SourceKind.sim, "p1041", clock.now),
        rehearsal.source,
        rehearsal.read_key,
        tmp_path,
        breathe_guide(rate, minutes),
        rate,
        clock=clock,
        sleep=lambda _: clock.advance(TICK_S),
        check=Preflight(wait_s=20.0),
        on_start=lambda: rehearsal.delay_script(rehearsal.now()),
    )
    assert code == 0
    assert report is not None
    before, pace = report.phases["before"], report.phases["pace"]
    assert before.moving_s == 0.0
    assert pace.moving_s >= 8.0
    assert pace.swing_ms is not None
    assert before.swing_ms is not None
    assert pace.swing_ms > 1.5 * before.swing_ms  # still seen with the moving seconds left out


def test_bad_rate_exits_2() -> None:
    result = CliRunner().invoke(app, ["breathe", "--source", "sim", "--rate", "20"])
    assert result.exit_code == EXIT_BAD_ARGS
    assert "--rate" in result.output


def test_breathe_refuses_replay() -> None:
    assert CliRunner().invoke(app, ["breathe", "--source", "play"]).exit_code == EXIT_BAD_ARGS


def test_an_exercise_plays_each_step_once_and_ends(capsys: pytest.CaptureFixture[str]) -> None:
    clock = FakeClock()
    guide = load("urge").guide()
    code = _play(guide, clock=clock, sleep=clock.advance, read_key=lambda: None)
    out = capsys.readouterr().out
    assert code == 0
    for _, text in load("urge").steps:
        assert out.count(text) == 1


def test_q_stops_an_exercise(capsys: pytest.CaptureFixture[str]) -> None:
    clock = FakeClock()
    keys = iter([None, None, "q"])
    code = _play(
        load("defusion").guide(),
        clock=clock,
        sleep=clock.advance,
        read_key=lambda: next(keys, None),
    )
    assert code == 0
    assert "Stopped." in capsys.readouterr().out


def test_an_exercise_can_record_on_the_simulator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mufuse.exercises import library
    from mufuse.guide import Guide

    short = library.Exercise("urge", "t", 2.0, ((0.0, "a"), (1.0, "b")))
    monkeypatch.setattr("mufuse.cli.load_exercise", lambda name: short)
    assert isinstance(short.guide(), Guide)
    result = CliRunner().invoke(
        app, ["exercise", "urge", "--source", "sim", "--out", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    (session,) = [p for p in tmp_path.iterdir() if p.is_dir()]
    labels = [m.label for m in load_session(session).markers]
    assert labels == ["x:urge:start", "x:urge:end"]
