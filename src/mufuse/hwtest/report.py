"""The guided test's report: Markdown to paste into the PR, JSON for tools."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from mufuse.acquisition import signal_check
from mufuse.hwtest.checks import EEG_NAMES, CheckResult, Condition, Timings


@dataclass
class Report:
    run_id: str
    run_dir: Path
    started_at: float
    finished_at: float
    bench: str
    practice: bool
    simulated: bool
    aborted: bool
    stop_reason: str
    device: dict[str, Any]
    environment: dict[str, str]
    timings: Timings
    results: list[CheckResult] = field(default_factory=list[CheckResult])
    sessions: dict[str, str] = field(default_factory=dict[str, str])

    def result(self, key: str) -> CheckResult:
        return next(r for r in self.results if r.key == key)

    def count(self, status: str) -> int:
        return sum(r.status == status for r in self.results)

    @property
    def passed(self) -> bool:
        return not self.aborted and self.count("fail") == 0 and self.count("pass") > 0

    def summary(self) -> str:
        ran = self.count("pass") + self.count("fail")
        text = f"{self.count('pass')} of {ran} checks passed"
        if self.count("skipped"):
            text += f", {self.count('skipped')} skipped"
        return text

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "bench": self.bench,
            "practice": self.practice,
            "simulated": self.simulated,
            "aborted": self.aborted,
            "stop_reason": self.stop_reason,
            "summary": self.summary(),
            "device": self.device,
            "environment": self.environment,
            "timings": asdict(self.timings),
            "results": [r.as_dict() for r in self.results],
            "sessions": self.sessions,
        }

    def write(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "report.json").write_text(
            json.dumps(self.as_dict(), indent=2, default=str), encoding="utf-8"
        )
        (self.run_dir / "report.md").write_text(render_markdown(self), encoding="utf-8")


def environment() -> dict[str, str]:
    env = {
        "mufuse": _version("mufuse"),
        "python": platform.python_version(),
        "os": platform.platform(),
    }
    commit = _git_commit()
    if commit:
        env["commit"] = commit
    return env


def _version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:  # pragma: no cover - always installed in practice
        return "unknown"


def _git_commit() -> str | None:
    git = shutil.which("git")
    if git is None:  # pragma: no cover - git is present wherever the repo is checked out
        return None
    try:
        out = subprocess.run(
            [git, "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - not a checkout
        return None
    return out.stdout.strip() or None


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown(report: Report) -> str:
    started = datetime.fromtimestamp(report.started_at, tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
    minutes = max(0.0, report.finished_at - report.started_at) / 60
    device = report.device
    firmware = device.get("firmware") or "not read"
    extra: dict[str, str] = device.get("extra") or {}
    if extra:
        firmware += " (" + ", ".join(f"{k} {v}" for k, v in sorted(extra.items())) + ")"
    env = report.environment
    software = f"MuFuse {env.get('mufuse', '?')}"
    if "commit" in env:
        software += f" ({env['commit']})"
    software += f" · Python {env.get('python', '?')} · {env.get('os', '?')}"

    lines = ["# MuFuse hardware test", "", f"**Result: {report.summary()}**", ""]
    if report.simulated:
        lines += ["> Simulated headband (dry run). No real hardware was tested.", ""]
    if report.practice:
        lines += ["> Practice run with shortened tests. Not valid as the acceptance record.", ""]
    if report.stop_reason:
        lines += [f"> The run stopped early: {report.stop_reason}.", ""]
    lines += [
        "| | |",
        "|---|---|",
        f"| Date | {started} |",
        f"| Headband | {_cell(str(device.get('name') or 'not found'))} |",
        f"| Firmware | {_cell(firmware)} |",
        f"| Preset | {device.get('preset', '?')} |",
        f"| Connection | {_cell(report.bench)} |",
        f"| Software | {_cell(software)} |",
        f"| Duration | {minutes:.0f} min |",
        "",
        "| # | Check | Spec | Result | Measured |",
        "|---|---|---|---|---|",
    ]
    for number, r in enumerate(report.results, 1):
        lines.append(
            f"| {number} | {_cell(r.title)} | {r.spec} | {r.status.upper()} | {_cell(r.measured)} |"
        )
    lines += ["", "## Pass criteria", ""]
    lines += [f"- **{r.title}:** {r.criterion}" for r in report.results if r.criterion]
    lines += _contact_section(report)
    if report.sessions:
        lines += ["", "## Test recordings", ""]
        lines += [f"- {purpose}: `{path}`" for purpose, path in report.sessions.items()]
    lines += [
        "",
        "Recordings stay on this computer (`recordings/` is git-ignored). "
        "Paste this report into the feature 001 pull request.",
        "",
    ]
    return "\n".join(lines)


def _contact_section(report: Report) -> list[str]:
    contact = next((r for r in report.results if r.key == "contact" and r.details), None)
    if contact is None:
        return []
    table: dict[str, dict[str, dict[str, float]]] = contact.details["conditions"]
    lines = [
        "",
        "## Sensor contact numbers",
        "",
        f"The most common status across {report.timings.contact_window_s:g}-second windows, "
        "with its share and the median signal spread. "
        "Use these to tune `src/mufuse/acquisition/signal_check.py` "
        f"(flat below {signal_check.FLAT_UV:g} µV, noisy above {signal_check.NOISY_UV:g} µV, "
        f"railed when over {100 * signal_check.RAIL_FRACTION:g}% of samples exceed "
        f"{signal_check.RAIL_UV:g} µV).",
        "",
        "| Condition | " + " | ".join(EEG_NAMES) + " |",
        "|---|" + "---|" * len(EEG_NAMES),
    ]
    for condition, channels in table.items():
        cells: list[str] = []
        for name in EEG_NAMES:
            row = channels[name]
            top = max(("ok", "flat", "noisy", "railed"), key=lambda s: row[s])
            cells.append(f"{top} {100 * row[top]:.0f}% · {row['spread_uv']:.1f} µV")
        lines.append(f"| {Condition(condition).label} | " + " | ".join(cells) + " |")
    return lines
