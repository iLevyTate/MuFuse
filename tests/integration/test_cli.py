from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from mufuse.acceptance import CHECKS, wearer_for
from mufuse.acquisition.simulated import Rehearsal, SimulatedAthena
from mufuse.acquisition.source import HeadbandSource
from mufuse.acquisition.types import SourceError
from mufuse.cli import (
    EXIT_BAD_ARGS,
    EXIT_CONNECT,
    EXIT_UNREADABLE,
    _read_key,  # pyright: ignore[reportPrivateUsage]
    app,
)
from mufuse.guide import Cue, Guide, action
from mufuse.recording.reader import load_session
from mufuse.runlog import log_path, read_runs

runner = CliRunner()


def test_record_then_inspect_with_simulated_source(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["record", "--source", "sim", "--duration", "1.0", "--out", str(tmp_path), "--notes", "ci"],
    )
    assert result.exit_code == 0, result.output
    (session_dir,) = tmp_path.iterdir()
    inspected = runner.invoke(app, ["inspect", str(session_dir)])
    assert inspected.exit_code == 0, inspected.output
    assert "finalized" in inspected.output
    assert "eeg" in inspected.output


def test_stream_with_simulated_source() -> None:
    result = runner.invoke(app, ["stream", "--source", "sim", "--duration", "0.5"])
    assert result.exit_code == 0, result.output


def test_invalid_preset_is_rejected_before_connecting() -> None:
    result = runner.invoke(app, ["stream", "--source", "sim", "--preset", "p9999"])
    assert result.exit_code == EXIT_BAD_ARGS
    assert "p1041" in result.output


def test_play_requires_path() -> None:
    result = runner.invoke(app, ["stream", "--source", "play"])
    assert result.exit_code == EXIT_BAD_ARGS


def test_inspect_unreadable(tmp_path: Path) -> None:
    result = runner.invoke(app, ["inspect", str(tmp_path)])
    assert result.exit_code == EXIT_UNREADABLE


def test_piped_output_has_no_banner() -> None:
    result = runner.invoke(app, ["stream", "--source", "sim", "--duration", "0.2"])
    assert result.exit_code == 0, result.output
    assert "Punk EEG." not in result.output


def test_stream_logs_time_to_first_eeg() -> None:
    result = runner.invoke(app, ["stream", "--source", "sim", "--duration", "0.5"])
    assert result.exit_code == 0, result.output
    assert "first EEG after" in result.output
    (run,) = read_runs(log_path())
    assert (run.command, run.source, run.outcome) == ("stream", "sim", "signal")
    assert run.seconds_to_signal is not None
    assert 0 <= run.seconds_to_signal < 5


def test_launcher_start_time_and_label_reach_the_log(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUFUSE_T0", str(time.time() - 100))
    monkeypatch.setenv("MUFUSE_RUN_LABEL", "H3 test 1/10")
    result = runner.invoke(app, ["stream", "--source", "sim", "--duration", "0.2"])
    assert result.exit_code == 0, result.output
    (run,) = read_runs(log_path())
    assert run.label == "H3 test 1/10"
    assert run.seconds_to_signal is not None
    assert run.seconds_to_signal >= 100


def test_connect_failure_is_logged(monkeypatch: pytest.MonkeyPatch) -> None:
    class Refuses(SimulatedAthena):
        def start(self) -> None:
            raise SourceError("BOARD_NOT_READY_ERROR:7 unable to prepare streaming session")

    monkeypatch.setattr("mufuse.acquisition.simulated.SimulatedAthena", Refuses)
    result = runner.invoke(app, ["stream", "--source", "sim", "--duration", "0.2"])
    assert result.exit_code == EXIT_CONNECT
    (run,) = read_runs(log_path())
    assert run.outcome == "connect_error"
    assert run.seconds_to_signal is None
    assert run.error is not None
    assert "BOARD_NOT_READY" in run.error


def test_guided_record_writes_cue_markers_at_their_scheduled_times(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    guide_file = tmp_path / "guide.json"
    Guide(cues=(Cue(0, "Keep still"), *action(0.6, "Do it", marker="did_it")), duration=1.0).save(
        guide_file
    )
    monkeypatch.setenv("MUFUSE_GUIDE", str(guide_file))
    out = tmp_path / "rec"
    result = runner.invoke(
        app, ["record", "--source", "sim", "--duration", "1.0", "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    (session_dir,) = out.iterdir()
    session = load_session(session_dir)
    (marker,) = session.markers
    assert (marker.kind, marker.label, marker.source) == ("system", "did_it", "system")
    assert marker.t - session.manifest["started_at"] == pytest.approx(0.6, abs=0.05)


# MUFUSE_SIM_WEARER: rehearsing a hardware check on the simulated headband -----------------


class _Handed:
    """What a command hands to the run loop, caught before anything connects."""

    factory: Callable[[], HeadbandSource]
    read_key: Callable[[], str | None]

    def run(self, *args: Any, read_key: Callable[[], str | None]) -> None:
        self.factory, self.read_key = args[1], read_key


@pytest.fixture
def handed(monkeypatch: pytest.MonkeyPatch) -> _Handed:
    caught = _Handed()
    monkeypatch.setattr("mufuse.cli._run", caught.run)
    return caught


@pytest.mark.parametrize("command", ["stream", "record"])
def test_the_wearer_variable_puts_a_scripted_wearer_on_the_simulated_headband(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, handed: _Handed, command: str
) -> None:
    monkeypatch.setenv("MUFUSE_SIM_WEARER", "H6")
    args = ["--out", str(tmp_path)] if command == "record" else []
    result = runner.invoke(app, [command, "--source", "sim", "--preset", "p1042", *args])
    assert result.exit_code == 0, result.output
    rehearsal = getattr(handed.factory, "__self__", None)
    assert isinstance(rehearsal, Rehearsal)
    assert rehearsal.wearer == wearer_for(CHECKS["H6"])
    device = handed.factory().device
    assert (device.firmware, device.preset) == ("3.1.19", "p1042")
    assert handed.read_key() is None  # nothing is due before the script begins
    rehearsal.t0 = time.time() - 60  # a minute in, every scripted press is due
    assert [handed.read_key() for _ in range(4)] == [" ", " ", " ", None]


def test_without_the_wearer_variable_the_simulated_headband_is_the_plain_one(
    handed: _Handed,
) -> None:
    result = runner.invoke(app, ["stream", "--source", "sim"])
    assert result.exit_code == 0, result.output
    assert type(handed.factory()) is SimulatedAthena
    assert handed.read_key is _read_key


def test_the_wearer_variable_is_only_read_for_the_simulated_headband(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, handed: _Handed
) -> None:
    monkeypatch.setenv("MUFUSE_SIM_WEARER", "not a check")
    result = runner.invoke(app, ["stream", "--source", "play", "--play", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert handed.read_key is _read_key


def test_an_unknown_wearer_is_refused_before_connecting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUFUSE_SIM_WEARER", "H9")
    result = runner.invoke(app, ["stream", "--source", "sim", "--duration", "0.2"])
    assert result.exit_code == EXIT_BAD_ARGS
    assert "MUFUSE_SIM_WEARER" in result.output
    assert "H8:idle" in result.output
    assert not log_path().exists()
