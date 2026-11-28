"""Timed exercise scripts (009), kept as TOML in `scripts/` and played as a `Guide`.

The texts are written for MuFuse. They describe what to do, in plain neutral words: no claims
about health and nothing said about the person.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from importlib import resources

from mufuse.guide import Cue, Guide

EXERCISES = ("defusion", "urge")


@dataclass(frozen=True)
class Exercise:
    id: str
    title: str
    duration_s: float
    steps: tuple[tuple[float, str], ...]

    def guide(self) -> Guide:
        cues = [
            Cue(at, text, f"x:{self.id}:start" if i == 0 else None)
            for i, (at, text) in enumerate(self.steps)
        ]
        cues.append(Cue(self.duration_s, "Done", f"x:{self.id}:end"))
        return Guide(cues=tuple(cues), duration=self.duration_s + 1.0, title=self.title)


def load(name: str) -> Exercise:
    if name not in EXERCISES:
        raise ValueError(f"unknown exercise {name!r}: one of {', '.join(EXERCISES)}")
    text = (
        resources.files("mufuse.exercises")
        .joinpath("scripts", f"{name}.toml")
        .read_text(encoding="utf-8")
    )
    raw = tomllib.loads(text)
    steps = tuple((float(s["at"]), str(s["text"])) for s in raw["step"])
    if [at for at, _ in steps] != sorted(at for at, _ in steps):
        raise ValueError(f"{name}: steps must be in time order")
    return Exercise(str(raw["id"]), str(raw["title"]), float(raw["duration_s"]), steps)
