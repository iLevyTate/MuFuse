"""The labelled session rehearsed end to end on a fake clock (SC-001 on the simulator).

A green run proves the pipeline (cues, markers, live judging, replay, scoring), not the physiology:
the simulated blinks, clenches, turns and lifts are guesses (`mufuse.acquisition.simulated`).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from mufuse.acquisition.simulated import CTRL_C, Rehearsal, SimulatedAthena, Wearer
from mufuse.acquisition.types import SourceError
from mufuse.cli import (
    EXIT_CONNECT,
    EXIT_INTERRUPTED,
    EXIT_WRITE,
    SourceKind,
    _Attempt,  # pyright: ignore[reportPrivateUsage]
    _label,  # pyright: ignore[reportPrivateUsage]
    app,
)
from mufuse.preflight import Preflight
from mufuse.quality.labelled import END_S, ScoreReport, rehearsal_wearer, schedule
from mufuse.recording.reader import load_session
from tests.conftest import FakeClock

TICK_S = 0.5  # the loop turns every 0.5 s in here; 9.5 minutes of session in a few seconds
QUICK = {"connect_s": 0.0, "first_data_s": 0.0, "scan_s": 0.0, "stop_s": 0.0}


@dataclass(frozen=True)
class Labelled:
    code: int
    report: ScoreReport | None
    folder: Path | None


def _label_run(out: Path, wearer: Wearer, clock: FakeClock) -> Labelled:
    rehearsal = Rehearsal(wearer, clock=clock, sleep=clock.advance)
    code, report, folder = _label(
        _Attempt("quality label", SourceKind.sim, "p1041", clock.now),
        rehearsal.source,
        rehearsal.read_key,
        out,
        clock=clock,
        sleep=lambda _: clock.advance(TICK_S),
    )
    return Labelled(code, report, folder)


@pytest.fixture(scope="module")
def rehearsed(tmp_path_factory: pytest.TempPathFactory) -> Labelled:
    out = tmp_path_factory.mktemp("labelled")
    return _label_run(out, replace(rehearsal_wearer(), **QUICK), FakeClock())


def test_the_rehearsed_session_scores_every_cue_and_passes(rehearsed: Labelled) -> None:
    assert rehearsed.code == 0
    report = rehearsed.report
    assert report is not None
    assert (report.blinks.found, report.blinks.total) == (20, 20)
    assert (report.clenches.found, report.clenches.total) == (20, 20)
    assert (report.turns.found, report.turns.total) == (20, 20)
    assert (report.lifts.found, report.lifts.total) == (10, 10)
    assert report.quiet.passed is True
    assert report.replay_identical is True
    assert report.passed


def test_the_cues_land_in_the_markers_at_their_times(rehearsed: Labelled) -> None:
    assert rehearsed.folder is not None
    session = load_session(rehearsed.folder)
    cues = [m for m in session.markers if m.label.startswith("q:")]
    assert [m.label for m in cues] == [c.label for c in schedule()]
    assert {m.kind for m in cues} == {"system"}
    first = cues[0].t - schedule()[0].t
    for marker, cue in zip(cues, schedule(), strict=True):
        assert marker.t - first == pytest.approx(cue.t)
    assert session.finalized


def test_quality_score_reads_the_session_back(rehearsed: Labelled) -> None:
    shown = CliRunner().invoke(app, ["quality", "score", str(rehearsed.folder)])
    assert shown.exit_code == 0, shown.output
    assert "Labelled session score (rules 1" in shown.output
    assert "replay        not checked" in shown.output
    assert "RESULT        pass" in shown.output


# The exit codes of `mufuse quality label` -----------------------------------------------------


def test_label_stopped_with_ctrl_c_keeps_the_session_and_exits_130(
    tmp_path: Path, clock: FakeClock
) -> None:
    wearer = replace(rehearsal_wearer(), keys=((30.0, CTRL_C),), **QUICK)
    run = _label_run(tmp_path, wearer, clock)
    assert run.code == EXIT_INTERRUPTED
    assert run.report is None
    assert run.folder is not None
    session = load_session(run.folder)
    assert session.finalized
    assert not any(m.label == "q:end" for m in session.markers)
    assert max(m.t for m in session.markers) - min(m.t for m in session.markers) < END_S


def test_label_that_cannot_connect_exits_4(tmp_path: Path, clock: FakeClock) -> None:
    class Off(SimulatedAthena):
        def start(self) -> None:
            raise SourceError("The simulated headband is switched off.")

    with pytest.raises(typer.Exit) as stopped:
        _label(
            _Attempt("quality label", SourceKind.sim, "p1041", clock.now),
            lambda: Off(clock=clock),
            lambda: None,
            tmp_path,
            clock=clock,
            sleep=clock.advance,
        )
    assert stopped.value.exit_code == EXIT_CONNECT


def test_label_that_cannot_write_exits_5(tmp_path: Path, clock: FakeClock) -> None:
    not_a_folder = tmp_path / "file"
    not_a_folder.write_text("", encoding="utf-8")
    with pytest.raises(typer.Exit) as stopped:
        _label_run(not_a_folder, replace(rehearsal_wearer(), **QUICK), clock)
    assert stopped.value.exit_code == EXIT_WRITE


# The pre-flight check before the first cue -------------------------------------------------------


def _checked_run(out: Path, wearer: Wearer, clock: FakeClock) -> Labelled:
    rehearsal = Rehearsal(wearer, clock=clock, sleep=clock.advance)
    code, report, folder = _label(
        _Attempt("quality label", SourceKind.sim, "p1041", clock.now),
        rehearsal.source,
        rehearsal.read_key,
        out,
        clock=clock,
        sleep=lambda _: clock.advance(TICK_S),
        check=Preflight(wait_s=20.0),
        on_start=lambda: rehearsal.delay_script(rehearsal.now()),
    )
    return Labelled(code, report, folder)


def _check_marker(folder: Path | None) -> str:
    assert folder is not None
    (label,) = [m.label for m in load_session(folder).markers if m.label.startswith("check:")]
    return label


def test_a_good_fit_starts_the_session_by_itself_and_it_still_passes(
    tmp_path: Path, clock: FakeClock
) -> None:
    run = _checked_run(tmp_path, replace(rehearsal_wearer(), **QUICK), clock)
    assert run.code == 0
    assert run.report is not None
    assert run.report.passed
    assert run.report.replay_identical is True
    assert _check_marker(run.folder) == "check:ready"


def test_a_forehead_that_never_fits_waits_for_the_wearer_to_start_anyway(
    tmp_path: Path, clock: FakeClock
) -> None:
    wearer = replace(rehearsal_wearer(), lifted=((0.0, 1e6, "AF7"),), keys=((25.0, "s"),), **QUICK)
    run = _checked_run(tmp_path, wearer, clock)
    assert run.code == 0  # recorded and scored: a missing sensor is not a show stopper
    assert run.report is not None
    assert not run.report.passed  # ... but AF7 out does cost the score
    assert _check_marker(run.folder) == "check:anyway:AF7"
    assert run.folder is not None
    session = load_session(run.folder)
    check = next(m.t for m in session.markers if m.label.startswith("check:"))
    first_cue = min(m.t for m in session.markers if m.label.startswith("q:"))
    assert check - session.manifest["started_at"] >= 20.0  # it waited the whole wait first
    assert first_cue - check == pytest.approx(schedule()[0].t, abs=TICK_S)


def test_q_at_the_check_stops_before_any_cue(tmp_path: Path, clock: FakeClock) -> None:
    wearer = replace(rehearsal_wearer(), lifted=((0.0, 1e6, "AF8"),), keys=((5.0, "q"),), **QUICK)
    run = _checked_run(tmp_path, wearer, clock)
    assert run.code == EXIT_INTERRUPTED
    assert run.folder is not None
    session = load_session(run.folder)
    assert session.finalized
    assert not [m for m in session.markers if m.label.startswith(("q:", "check:"))]


def test_quality_label_checks_the_fit_unless_told_not_to(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[Preflight | None] = []

    def fake_label(
        *args: object, check: Preflight | None, **kwargs: object
    ) -> tuple[int, None, None]:
        seen.append(check)
        return 0, None, None

    monkeypatch.setattr("mufuse.cli._label", fake_label)
    runner = CliRunner()
    assert (
        runner.invoke(
            app, ["quality", "label", "--source", "sim", "--out", str(tmp_path)]
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app, ["quality", "label", "--source", "sim", "--no-check", "--out", str(tmp_path)]
        ).exit_code
        == 0
    )
    assert isinstance(seen[0], Preflight)
    assert seen[1] is None
