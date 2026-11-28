"""Interpreters: guesses about a moment, each declared in a manifest and kept silent until it
beats chance on the wearer's own random check-ins (006 decisions 3-5, 9-10; constitution V).

Only first-party interpreters exist and they are listed in `REGISTRY`; nothing is loaded from
elsewhere. A manifest is TOML (stdlib `tomllib`) and its phrasing is fixed: code fills in counts,
never words about the person.
"""

from __future__ import annotations

import tomllib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib import resources
from typing import Literal, Protocol

import numpy as np

from mufuse.features.engine import FeatureFrame

Tier = Literal["grounded", "extrapolated", "speculative"]
EARLY_TAG = "speculative · unproven for you"


@dataclass(frozen=True)
class Manifest:
    id: str
    version: int
    title: str
    tier: Tier
    target: tuple[str, ...]
    needs: tuple[str, ...]
    needs_share: float
    window_s: float
    threshold: float
    looks: tuple[int, ...]
    phrasing: str

    @classmethod
    def parse(cls, text: str) -> Manifest:
        raw = tomllib.loads(text)
        tier = raw["tier"]
        if tier not in ("grounded", "extrapolated", "speculative"):
            raise ValueError(f"unknown tier {tier!r}")
        if float(raw["window_s"]) < 15.0:
            raise ValueError("window_s must be at least 15 s (Muse indices need the smoothing)")
        looks = tuple(int(x) for x in raw["looks"])
        if not looks or list(looks) != sorted(set(looks)):
            raise ValueError("looks must be increasing counts, fixed in advance")
        if "you are" in str(raw["phrasing"]).lower():
            raise ValueError("phrasing describes signals, never the person")
        return cls(
            id=str(raw["id"]),
            version=int(raw["version"]),
            title=str(raw["title"]),
            tier=tier,
            target=tuple(str(x) for x in raw["target"]),
            needs=tuple(str(x) for x in raw["needs"]),
            needs_share=float(raw["needs_share"]),
            window_s=float(raw["window_s"]),
            threshold=float(raw["threshold"]),
            looks=looks,
            phrasing=str(raw["phrasing"]),
        )

    def say(self, *, hits: int = 0, fired: int = 0, early: bool) -> str:
        """The approved phrasing, with counts from code once there are any, and the early tag."""
        counts = ""
        if fired:
            answers = " or ".join(self.target)
            counts = f", which in your random check-ins went with {answers} {hits} of {fired} times"
        text = self.phrasing.format(counts=counts)
        return f"{text} ({EARLY_TAG})" if early else text


class Interpreter(Protocol):
    manifest: Manifest

    def score(self, frames: Sequence[FeatureFrame]) -> float | None:
        """Higher = more like the target answers; None when the window holds too little."""
        ...


def window(frames: Sequence[FeatureFrame], end: float, seconds: float) -> list[FeatureFrame]:
    """The frames of the `seconds` before `end`."""
    return [f for f in frames if end - seconds < f.t <= end]


def _manifest(name: str) -> Manifest:
    text = (
        resources.files("mufuse.observe")
        .joinpath("manifests", f"{name}.toml")
        .read_text(encoding="utf-8")
    )
    return Manifest.parse(text)


@dataclass
class AttentionDrift:
    """Blink rate and alpha share both up on the baseline (006 decision 4). Speculative."""

    manifest: Manifest

    def score(self, frames: Sequence[FeatureFrame]) -> float | None:
        m = self.manifest
        if not frames:
            return None
        means: list[float] = []
        for series in m.needs:
            zs = [z for f in frames if (z := f.z.get(series)) is not None]
            if len(zs) < m.needs_share * len(frames):
                return None
            means.append(float(np.mean(zs)))
        return float(np.mean(means))


REGISTRY: dict[str, Callable[[], Interpreter]] = {
    "attention_drift": lambda: AttentionDrift(_manifest("attention_drift")),
}


def load_all() -> list[Interpreter]:
    return [make() for make in REGISTRY.values()]
