from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mufuse.cli import EXIT_BAD_ARGS, EXIT_UNREADABLE, app

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
