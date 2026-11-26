"""The one-sitting command end to end on the simulator, with each recording run in-process.

The launcher's child process is replaced by the real record loop on the fake clock, fed the same
command line and environment the child would get, so the notes, the guide, the simulated wearer,
the judges, the results file and a later re-judgement are all the real ones.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer

from mufuse.acceptance import wearer_from_env
from mufuse.acquisition.simulated import Rehearsal
from mufuse.cli import (
    SourceKind,
    _Attempt,  # pyright: ignore[reportPrivateUsage]
    _run,  # pyright: ignore[reportPrivateUsage]
)
from mufuse.recording.writer import SessionWriter
from mufuse.sitting import FAIL, PASS, SKIPPED, main, read_rows
from tests.conftest import FakeClock

REPO = Path(__file__).resolve().parents[2]
TICK_S = 0.25  # as in test_rehearsal: the same loop on a fifth of the turns


class Recorder:
    """Stands in for `mufuse record` as a child process."""

    def __init__(self, clock: FakeClock, monkeypatch: pytest.MonkeyPatch) -> None:
        self.clock = clock
        self.monkeypatch = monkeypatch
        self.wearers: list[str] = []
        self.idle = False  # a wearer who ignores every cue

    def __call__(self, cmd: list[str], env: dict[str, str], cwd: Path | None) -> int:
        assert cmd[1] == "record", cmd
        options = dict(zip(cmd[2::2], cmd[3::2], strict=True))
        assert options["--source"] == "sim"
        assert env["PYTHONUTF8"] == "1"
        self.wearers.append(env["MUFUSE_SIM_WEARER"])
        for name in ("MUFUSE_GUIDE", "MUFUSE_RUN_LABEL", "MUFUSE_LOG_DIR"):
            self.monkeypatch.setenv(name, env[name])
        variant = ":idle" if self.idle else ""
        self.monkeypatch.setenv("MUFUSE_SIM_WEARER", env["MUFUSE_SIM_WEARER"] + variant)
        wearer = wearer_from_env()
        assert wearer is not None
        clock = self.clock
        rehearsal = Rehearsal(wearer, clock=clock, sleep=clock.advance)
        try:
            _run(
                _Attempt("record", SourceKind.sim, "p1041", clock.now),
                rehearsal.source,
                float(options["--duration"]),
                lambda src: SessionWriter.create(
                    Path(options["--out"]),
                    src.device,
                    src.streams,
                    notes=options["--notes"],
                    clock=clock,
                ),
                clock=clock,
                sleep=lambda _: clock.advance(TICK_S),
                read_key=rehearsal.read_key,
            )
        except typer.Exit as stopped:
            return int(stopped.exit_code)
        return 0


def _rehearse(argv: list[str], recorder: Recorder, out: Path) -> int:
    clock = recorder.clock
    return main(
        ["--rehearse", "--out", str(out), *argv],
        repo=REPO,
        spawn=recorder,
        clock=clock,
        sleep=clock.advance,
    )


def test_a_rehearsal_runs_unattended_and_leaves_rows_and_sessions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clock: FakeClock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    logs = tmp_path / "logs"
    monkeypatch.setenv("MUFUSE_LOG_DIR", str(logs))
    recorder = Recorder(clock, monkeypatch)

    code = _rehearse(["--h4-seconds", "30", "P0", "H7", "H4", "H1/H2"], recorder, tmp_path / "out")

    shown = capsys.readouterr().out
    assert code == 1, shown  # H1/H2 cannot be rehearsed, so the run as a whole has not passed
    assert recorder.wearers == ["P0", "H7", "H4"]
    rows = read_rows(logs / "acceptance.jsonl")
    attempts = [r for r in rows if r["kind"] == "attempt"]
    assert [(r["check"], r["outcome"]) for r in attempts] == [
        ("P0", PASS),
        ("H7", PASS),  # stopped by the simulated Ctrl+C, and saved
        ("H4", PASS),
        ("H1/H2", SKIPPED),
    ], shown
    assert {r["source"] for r in rows} == {"sim"}
    sessions = sorted(p.name for p in (tmp_path / "out").iterdir())
    assert [r["session"] for r in attempts[:3]] == sessions
    assert attempts[0]["firmware"] == "3.1.19"
    assert attempts[0]["measures"]
    assert "3 of 4 passed" in shown
    assert "not hardware evidence" in shown
    report = logs / "acceptance" / rows[0]["run"] / "report.md"
    assert f"Report: {report}" in shown
    text = report.read_text(encoding="utf-8")
    assert "SIMULATOR REHEARSAL: not hardware evidence" in text.splitlines()[2]
    assert "3 of 4 requested checks passed" in text
    assert "--rehearse --h4-seconds 30 P0 H7 H4 H1/H2" in text
    assert "| P0 sitting still |" in text  # the calibration tables, from the real judges
    assert "| H4 whole recording" in text
    assert "- H1/H2: SKIPPED. Reason: the hardware tests need the real headband." in text
    for private in (str(tmp_path), tmp_path.name, "Users", *sessions):
        assert private not in text, private


def test_a_failed_check_can_be_judged_again_from_what_was_saved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clock: FakeClock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    logs = tmp_path / "logs"
    out = tmp_path / "out"
    monkeypatch.setenv("MUFUSE_LOG_DIR", str(logs))
    recorder = Recorder(clock, monkeypatch)
    recorder.idle = True  # nobody lifts the ear sensor: H8 must fail

    assert _rehearse(["H8"], recorder, out) == 1
    first = capsys.readouterr().out
    (session,) = out.iterdir()
    assert f'--rejudge "{session}"' in first
    ledger = logs / "acceptance.jsonl"
    earlier = ledger.read_text(encoding="utf-8")
    run = json.loads(earlier.splitlines()[0])["run"]

    assert main(["--rejudge", run, "--out", str(out)], repo=REPO) == 1

    assert ledger.read_text(encoding="utf-8").startswith(earlier)
    attempt, again = [r for r in read_rows(ledger) if r["kind"] in ("attempt", "rejudge")]
    assert (again["kind"], again["outcome"], again["attempt"]) == ("rejudge", FAIL, 1)
    assert again["lines"] == attempt["lines"]  # the same judges on the same saved session
    assert again["session"] == session.name
    assert again["source"] == "sim"
    shown = capsys.readouterr().out
    assert "H8: FAIL" in shown
    report = logs / "acceptance" / run / "report.md"
    assert f"Report: {report}" in shown
    assert "| FAIL (judged again, same outcome) | 1 |" in report.read_text(encoding="utf-8")


def test_resume_runs_only_what_the_rehearsal_did_not_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clock: FakeClock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("MUFUSE_LOG_DIR", str(tmp_path / "logs"))
    recorder = Recorder(clock, monkeypatch)
    recorder.idle = True
    assert _rehearse(["P0", "H6"], recorder, tmp_path / "out") == 1  # no SPACE was pressed
    recorder.idle = False
    recorder.wearers.clear()

    assert _rehearse(["--resume"], recorder, tmp_path / "out") == 0

    assert recorder.wearers == ["H6"]
    assert "2 of 2 passed" in capsys.readouterr().out
    assert _rehearse(["--resume"], recorder, tmp_path / "out") == 0
    assert "Every check of run" in capsys.readouterr().out
