from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from mufuse.cli import EXIT_BAD_ARGS, EXIT_CHECKS_FAILED, EXIT_UNREADABLE, app
from tests.conftest import FAST_TIMINGS

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


def test_hardware_test_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("mufuse.cli.hwtest_timings", lambda quick: FAST_TIMINGS)
    result = runner.invoke(
        app, ["hardware-test", "--dry-run", "--only", "find,firmware", "--out", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "report.md" in result.output
    assert "2 of 2 checks passed" in result.output


def test_hardware_test_reports_failures_in_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mufuse.hwtest import simulated

    real_bench = simulated.simulated_bench
    monkeypatch.setattr("mufuse.cli.hwtest_timings", lambda quick: FAST_TIMINGS)
    monkeypatch.setattr(
        "mufuse.cli.simulated_bench", lambda console: real_bench(console, devices=[])
    )
    result = runner.invoke(app, ["hardware-test", "--dry-run", "--out", str(tmp_path)])
    assert result.exit_code == EXIT_CHECKS_FAILED, result.output


def test_hardware_test_rejects_unknown_check() -> None:
    result = runner.invoke(app, ["hardware-test", "--dry-run", "--only", "bogus"])
    assert result.exit_code == EXIT_BAD_ARGS
    assert "interrupt" in result.output  # lists the valid names


def test_piped_output_has_no_banner() -> None:
    result = runner.invoke(app, ["stream", "--source", "sim", "--duration", "0.2"])
    assert result.exit_code == 0, result.output
    assert "Punk EEG." not in result.output
