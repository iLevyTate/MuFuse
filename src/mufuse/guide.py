"""Timed on-screen cues for guided sessions, e.g. the hardware acceptance run.

A guide is a list of cues, each shown from its `at` (seconds after streaming starts) until the
next one, with a countdown. Cues that carry a `marker` also write a system marker into the
recording at their scheduled time, so checks can compare what was asked with what happened.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

READY_S = 3.0  # every action gets this long a "get ready" countdown
_ACTION, _NOW = ">> ", " now"
StepState = str  # "done" | "now" | "next" | "later"


@dataclass(frozen=True)
class Cue:
    at: float
    text: str
    marker: str | None = None


def action(at: float, text: str, marker: str | None = None, ready: float = READY_S) -> list[Cue]:
    """A get-ready countdown, then the instruction itself at `at`."""
    return [Cue(at - ready, f"Get ready: {text}"), Cue(at, f"{_ACTION}{text}{_NOW}", marker)]


@dataclass
class Guide:
    cues: tuple[Cue, ...]
    duration: float
    title: str = ""
    _fired: set[int] = field(default_factory=set[int], repr=False, compare=False)

    def prompt(self, elapsed: float) -> str:
        if elapsed >= self.duration:
            return "Done, stopping"
        text, left = self._now(elapsed)
        return f"{text} · {_clock(left)}"

    def current(self, elapsed: float) -> tuple[str, float]:
        """The instruction showing now, without the action marks, and the seconds until the
        next cue (or the end)."""
        if elapsed >= self.duration:
            return "Done, stopping", 0.0
        text, left = self._now(elapsed)
        return text.removeprefix(_ACTION).removesuffix(_NOW), left

    def _now(self, elapsed: float) -> tuple[str, float]:
        current, upcoming = None, self.duration
        for cue in self.cues:
            if cue.at > elapsed:
                upcoming = cue.at
                break
            current = cue
        return (current.text if current else "Starting"), upcoming - elapsed

    def timeline(self, elapsed: float) -> list[tuple[float, str, StepState]]:
        """The steps (cues other than get-ready countdowns), each marked done/now/next/later."""
        steps = [c for c in self.cues if not c.text.startswith("Get ready")]
        current = max((i for i, c in enumerate(steps) if c.at <= elapsed), default=-1)
        if elapsed >= self.duration:
            current = len(steps)
        return [
            (cue.at, cue.text.removeprefix(_ACTION).removesuffix(_NOW), _state(i, current))
            for i, cue in enumerate(steps)
        ]

    def clock(self, elapsed: float) -> str:
        """Elapsed and total time, e.g. "0:23 / 1:15"."""
        return f"{_mmss(min(elapsed, self.duration))} / {_mmss(self.duration)}"

    def due(self, elapsed: float) -> list[tuple[str, float]]:
        """Markers whose time has come, each returned once as (label, scheduled offset)."""
        out: list[tuple[str, float]] = []
        for i, cue in enumerate(self.cues):
            if cue.marker and cue.at <= elapsed and i not in self._fired:
                self._fired.add(i)
                out.append((cue.marker, cue.at))
        return out

    def save(self, path: Path) -> None:
        payload = {
            "title": self.title,
            "duration": self.duration,
            "cues": [asdict(c) for c in self.cues],
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Guide:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            cues=tuple(Cue(**c) for c in raw["cues"]),
            duration=float(raw["duration"]),
            title=raw.get("title", ""),
        )


def guide_from_env() -> Guide | None:
    """The guide a launcher handed over in MUFUSE_GUIDE, if any."""
    path = os.environ.get("MUFUSE_GUIDE")
    return Guide.load(Path(path)) if path else None


def _clock(seconds: float) -> str:
    whole = math.ceil(seconds - 1e-9)
    return f"{whole // 60}:{whole % 60:02d}" if whole >= 60 else f"{whole} s"


def _state(step: int, current: int) -> StepState:
    if step < current:
        return "done"
    if step == current:
        return "now"
    return "next" if step == current + 1 else "later"


def _mmss(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 60}:{whole % 60:02d}"
