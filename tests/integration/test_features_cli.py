"""`mufuse features`, its CSV, the resting wearer, and the frozen reference frames (003)."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mufuse.acceptance import wearer_from_env
from mufuse.cli import EXIT_UNREADABLE, app
from mufuse.features.engine import SERIES, WITH_BASELINE
from mufuse.features.params import FEATURES_VERSION
from tests.features_reference import REFERENCE, reference_frames, to_json

runner = CliRunner()


@pytest.fixture(scope="module")
def resting_session(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("rec")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("MUFUSE_SIM_WEARER", "resting")
        result = runner.invoke(
            app, ["record", "--source", "sim", "--duration", "12", "--out", str(out)]
        )
    assert result.exit_code == 0, result.output
    (session,) = [p for p in out.iterdir() if p.is_dir()]
    return session


def test_the_resting_wearer_is_a_simulator_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUFUSE_SIM_WEARER", "resting")
    wearer = wearer_from_env()
    assert wearer is not None
    assert wearer.resting


def test_features_prints_a_line_per_series_with_the_versions(resting_session: Path) -> None:
    result = runner.invoke(app, ["features", str(resting_session)])
    assert result.exit_code == 0, result.output
    assert f"features {FEATURES_VERSION}" in result.output
    for name in SERIES:
        assert name in result.output
    assert "not how you are" in result.output


def test_features_writes_one_csv_row_per_second(resting_session: Path, tmp_path: Path) -> None:
    out = tmp_path / "f.csv"
    result = runner.invoke(app, ["features", str(resting_session), "--csv", str(out)])
    assert result.exit_code == 0, result.output
    with out.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows
    assert set(rows[0]) == {"t", "features", "rules", *SERIES, *(f"z_{s}" for s in WITH_BASELINE)}
    assert {r["features"] for r in rows} == {FEATURES_VERSION}
    assert any(r["exponent"] for r in rows)


def test_features_of_an_unreadable_session_exits_6(tmp_path: Path) -> None:
    result = runner.invoke(app, ["features", str(tmp_path / "missing")])
    assert result.exit_code == EXIT_UNREADABLE


def _close(a: object, b: object) -> bool:
    if a is None or b is None:
        return a is b
    assert isinstance(a, float | int)
    assert isinstance(b, float | int)
    return math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-9)


def test_the_frames_match_the_frozen_reference() -> None:
    """A failure here means features changed: if meant, rerun the script and raise the version."""
    stored = json.loads(REFERENCE.read_text(encoding="utf-8"))
    now = to_json(reference_frames())
    assert stored["features"] == FEATURES_VERSION
    frames_now, frames_stored = now["frames"], stored["frames"]
    assert isinstance(frames_now, list)
    assert len(frames_now) == len(frames_stored)
    for got, want in zip(frames_now, frames_stored, strict=True):
        for part in ("values", "z"):
            for name, value in want[part].items():
                assert _close(got[part][name], value), (want["t"], part, name, got[part][name])


def test_the_reference_holds_every_kind_of_value() -> None:
    stored = json.loads(REFERENCE.read_text(encoding="utf-8"))
    for name in SERIES:
        assert any(f["values"][name] is not None for f in stored["frames"]), name
