"""`mufuse interpreters` and `mufuse interpreters feedback` (006)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from mufuse.cli import EXIT_BAD_ARGS, app
from mufuse.companion.store import Store

runner = CliRunner()


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "mufuse.db"
    monkeypatch.setattr("mufuse.companion.store.default_path", lambda: path)
    return path


def test_the_list_shows_shadow_mode_and_not_yet_known(db: Path) -> None:
    result = runner.invoke(app, ["interpreters"])
    assert result.exit_code == 0, result.output
    assert (
        "attention_drift v1 (Attention drift, speculative): shadow, early feedback off"
        in result.output
    )
    assert "random answers scored 0, next look at 50" in result.output
    assert "not yet known" in result.output


def test_early_feedback_switches_on_and_off_in_one_action(db: Path) -> None:
    assert runner.invoke(app, ["interpreters", "feedback", "on"]).exit_code == 0
    assert Store(db).interpreter("attention_drift").early is True
    assert "early feedback on" in runner.invoke(app, ["interpreters"]).output
    assert runner.invoke(app, ["interpreters", "feedback", "off"]).exit_code == 0
    assert Store(db).interpreter("attention_drift").early is False


def test_a_wrong_switch_or_id_is_refused(db: Path) -> None:
    assert runner.invoke(app, ["interpreters", "feedback", "maybe"]).exit_code == EXIT_BAD_ARGS
    assert (
        runner.invoke(app, ["interpreters", "feedback", "on", "--id", "nope"]).exit_code
        == EXIT_BAD_ARGS
    )
