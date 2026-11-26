"""The guided hardware test, end to end, against the simulated headband and a simulated person."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from rich.console import Console

from mufuse.hwtest.checks import CHECK_ORDER
from mufuse.hwtest.operator import Action
from mufuse.hwtest.runner import HardwareTest
from mufuse.hwtest.simulated import simulated_bench
from tests.conftest import FAST_TIMINGS


def _console() -> Console:
    return Console(file=io.StringIO(), width=100)


def test_dry_run_passes_every_check(tmp_path: Path) -> None:
    screen = io.StringIO()
    console = Console(file=screen, width=100)
    report = HardwareTest(simulated_bench(console), tmp_path, timings=FAST_TIMINGS).run()

    failures = {r.key: r.measured for r in report.results if r.status != "pass"}
    assert not failures
    assert [r.key for r in report.results] == list(CHECK_ORDER)
    assert report.passed
    assert not report.aborted

    markdown = (report.run_dir / "report.md").read_text(encoding="utf-8")
    assert "Simulated headband" in markdown
    assert "9 of 9 checks passed" in markdown
    data = json.loads((report.run_dir / "report.json").read_text(encoding="utf-8"))
    assert data["results"][0]["key"] == "find"
    assert data["device"]["firmware"] == "sim-1.0"
    sessions = sorted((report.run_dir / "sessions").iterdir())
    assert len(sessions) == 3  # 10-minute recording, power-off recording, Ctrl+C recording
    manifest = json.loads((sessions[0] / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["device"]["firmware"] == "sim-1.0"

    printed = screen.getvalue()
    assert "Switch the headband OFF now" in printed
    assert "Press SPACE now" in printed


def test_headband_left_on_fails_power_check(tmp_path: Path) -> None:
    bench = simulated_bench(_console(), ignore={Action.POWER_OFF, Action.POWER_ON})
    report = HardwareTest(bench, tmp_path, timings=FAST_TIMINGS, only={"power"}).run()
    assert report.result("power").status == "fail"
    assert "never stopped" in report.result("power").measured
    assert report.result("record").status == "skipped"
    assert not report.passed


def test_missed_space_presses_fail_markers_only(tmp_path: Path) -> None:
    bench = simulated_bench(_console(), ignore={Action.PRESS_SPACE})
    report = HardwareTest(bench, tmp_path, timings=FAST_TIMINGS, only={"markers"}).run()
    assert report.result("record").status == "pass"
    assert report.result("markers").status == "fail"
    assert "0 of 3" in report.result("markers").measured


def test_no_ctrl_c_fails_interrupt_check(tmp_path: Path) -> None:
    bench = simulated_bench(_console(), ignore={Action.PRESS_CTRL_C})
    report = HardwareTest(bench, tmp_path, timings=FAST_TIMINGS, only={"interrupt"}).run()
    assert report.result("interrupt").status == "fail"
    assert "No Ctrl+C" in report.result("interrupt").measured


def test_no_headband_found_skips_the_rest(tmp_path: Path) -> None:
    bench = simulated_bench(_console(), devices=[])
    report = HardwareTest(bench, tmp_path, timings=FAST_TIMINGS).run()
    assert report.result("find").status == "fail"
    later = [r for r in report.results if r.key != "find"]
    assert all(r.status == "skipped" for r in later)
    assert (report.run_dir / "report.md").exists()


def test_ctrl_c_between_steps_stops_and_keeps_the_report(tmp_path: Path) -> None:
    bench = simulated_bench(_console(), abort_at_prompt=3)
    report = HardwareTest(bench, tmp_path, timings=FAST_TIMINGS).run()
    assert report.aborted
    assert report.result("find").status == "pass"
    assert report.results[-1].status == "skipped"
    assert "stopped" in (report.run_dir / "report.md").read_text(encoding="utf-8")


def test_practice_run_is_labelled(tmp_path: Path) -> None:
    report = HardwareTest(
        simulated_bench(_console()), tmp_path, timings=FAST_TIMINGS, only={"find"}, practice=True
    ).run()
    assert "Practice run" in (report.run_dir / "report.md").read_text(encoding="utf-8")


def test_unknown_check_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="bogus"):
        HardwareTest(simulated_bench(_console()), tmp_path, timings=FAST_TIMINGS, only={"bogus"})
