"""Connection log: one JSON line per stream/record attempt, for acceptance runs like H3 (SC-001)."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from platformdirs import user_log_path

from mufuse.acquisition.types import Chunk, StreamKind

Outcome = str  # "signal" | "no_signal" | "connect_error" | "interrupted" | "timeout"


@dataclass(frozen=True)
class ConnectRun:
    at: str  # local ISO time the command started
    command: str
    source: str
    device: str | None
    preset: str
    outcome: Outcome
    seconds_to_signal: float | None  # command start -> first EEG sample
    elapsed_s: float  # command start -> signal, failure or stop
    error: str | None = None
    label: str | None = None  # set by launchers, e.g. "H3 20261126-0930 3/10"


class TimeToSignal:
    """Seconds from `t0` (command start) to the first non-empty EEG chunk, reported once."""

    def __init__(self, t0: float) -> None:
        self.t0 = t0
        self.seconds: float | None = None

    def observe(self, chunks: Sequence[Chunk], now: float) -> float | None:
        if self.seconds is not None:
            return None
        if any(c.kind is StreamKind.EEG and c.n_samples for c in chunks):
            self.seconds = now - self.t0
            return self.seconds
        return None


def log_path() -> Path:
    override = os.environ.get("MUFUSE_LOG_DIR")
    folder = Path(override) if override else user_log_path("mufuse", appauthor=False)
    return folder / "connect.jsonl"


def append_run(run: ConnectRun, path: Path | None = None) -> None:
    path = path or log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(run)) + "\n")


def read_runs(path: Path | None = None) -> list[ConnectRun]:
    path = path or log_path()
    if not path.exists():
        return []
    runs: list[ConnectRun] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            runs.append(ConnectRun(**json.loads(line)))
        except (json.JSONDecodeError, TypeError):
            continue  # a line torn by a crash mid-write
    return runs


@dataclass(frozen=True)
class Summary:
    passed: int
    attempts: int
    ok: bool


def summarize(runs: Sequence[ConnectRun], threshold_s: float, need: int) -> Summary:
    """An attempt passes when EEG arrived within `threshold_s`; any other outcome is a fail."""
    passed = sum(
        1 for r in runs if r.seconds_to_signal is not None and r.seconds_to_signal <= threshold_s
    )
    return Summary(passed=passed, attempts=len(runs), ok=passed >= need)
