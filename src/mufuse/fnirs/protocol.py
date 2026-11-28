"""The fNIRS validation protocol and its scorer (004 decisions 6-7). EXPERIMENTAL.

As in 002's labelled session, the cue is the label: one schedule drives the screen, the `f:`
markers in the recording, the rehearsal's scripted wearer and the scorer. A green rehearsal proves
the pipeline, not the physiology: the simulated responses are guesses.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, cast, get_args

import numpy as np

from mufuse.acquisition.simulated import Wearer
from mufuse.fnirs.mbll import EXPERIMENTAL, FNIRS_VERSION
from mufuse.fnirs.pipeline import Hemo
from mufuse.guide import Cue, Guide, action
from mufuse.recording.format import Marker

FKind = Literal["rest", "hold", "arith", "end"]
PREFIX = "f:"
REST_AT = 20.0
HOLDS = tuple(90.0 + 60.0 * k for k in range(5))
HOLD_S = 20.0
ARITHS = tuple(400.0 + 60.0 * k for k in range(5))
ARITH_S = 30.0
END_S = 700.0
RUN_S = 702.0  # the recording runs past `f:end` so that the marker is written
COUNT_FROM = (1000, 873, 951, 742, 806)
WINDOWS: dict[str, tuple[float, float]] = {"hold": (15.0, 35.0), "arith": (5.0, 30.0)}
BEFORE_S = 5.0  # the block's change is against the mean of the 5 s before its onset
MIN_COVER = 0.5  # a window with fewer used samples than this is not scored
PASS_SHARE = 0.7
REACT_S = 0.4  # the rehearsal's wearer follows a cue this late


@dataclass(frozen=True)
class FCue:
    t: float
    kind: FKind

    @property
    def label(self) -> str:
        return f"{PREFIX}{self.kind}"

    @classmethod
    def parse(cls, t: float, label: str) -> FCue | None:
        kind = label.removeprefix(PREFIX)
        if not label.startswith(PREFIX) or kind not in get_args(FKind):
            return None
        return cls(t, cast(FKind, kind))


def schedule() -> tuple[FCue, ...]:
    cues = [FCue(REST_AT, "rest")]
    cues += [FCue(t, "hold") for t in HOLDS]
    cues += [FCue(t, "arith") for t in ARITHS]
    cues.append(FCue(END_S, "end"))
    return tuple(cues)


def protocol_guide() -> Guide:
    cues = [Cue(0.0, "Settle: sit still, eyes open, breathe normally")]
    cues += action(REST_AT, "Sit still and rest, eyes open", "f:rest")
    cues.append(Cue(80.0, "Next: five breath-holds of 20 s"))
    for k, t in enumerate(HOLDS, 1):
        text = f"Breathe out normally, then hold your breath (Hold {k} of 5)"
        cues += action(t, text, "f:hold")
        cues.append(Cue(t + HOLD_S, f"Breathe again and rest (Hold {k} of 5)"))
    cues.append(Cue(390.0, "Next: count down by 7, silently, for 30 s"))
    for k, (t, start) in enumerate(zip(ARITHS, COUNT_FROM, strict=True), 1):
        cues += action(t, f"Count down by 7 from {start}, silently (Count {k} of 5)", "f:arith")
        cues.append(Cue(t + ARITH_S, f"Stop counting and rest (Count {k} of 5)"))
    cues.append(Cue(END_S, "Done. Saving and scoring", "f:end"))
    return Guide(cues=tuple(cues), duration=RUN_S, title="fNIRS protocol (004, experimental)")


def rehearsal_wearer(react_s: float = REACT_S) -> Wearer:
    """A simulated wearer whose forehead answers each block as the scorer expects (a guess)."""
    hemo = [(t + react_s + 8.0, t + react_s + 38.0, 1.0) for t in HOLDS]
    hemo += [(t + react_s + 3.0, t + react_s + 33.0, 0.6) for t in ARITHS]
    return Wearer(hemo=tuple(hemo))


def cues_from_markers(markers: Sequence[Marker]) -> tuple[FCue, ...]:
    found = (FCue.parse(m.t, m.label) for m in markers if m.kind == "system")
    return tuple(sorted((c for c in found if c is not None), key=lambda c: c.t))


@dataclass(frozen=True)
class Block:
    kind: str
    onset: float  # seconds after the first cue
    change_um: float | None  # None: not scored (too little used signal)

    @property
    def expected(self) -> bool | None:
        return None if self.change_um is None else self.change_um > 0


@dataclass(frozen=True)
class FnirsScore:
    blocks: tuple[Block, ...]
    version: str = FNIRS_VERSION

    @property
    def scored(self) -> list[Block]:
        return [b for b in self.blocks if b.expected is not None]

    @property
    def share(self) -> float | None:
        scored = self.scored
        return sum(bool(b.expected) for b in scored) / len(scored) if scored else None

    @property
    def passed(self) -> bool:
        return self.share is not None and self.share >= PASS_SHARE


def _mean(x: np.ndarray, t: np.ndarray, start: float, end: float) -> float | None:
    inside = (t >= start) & (t < end)
    if not inside.any() or np.isfinite(x[inside]).mean() < MIN_COVER:
        return None
    return float(np.nanmean(x[inside]))


def score(hemo: Hemo, cues: Sequence[FCue]) -> FnirsScore:
    """Per block: outer-detector ΔHbO in its window minus the 5 s before onset."""
    x, t = hemo.outer_hbo(), hemo.t
    first = cues[0].t if cues else 0.0
    blocks: list[Block] = []
    for cue in cues:
        if cue.kind not in WINDOWS:
            continue
        a, b = WINDOWS[cue.kind]
        during = _mean(x, t, cue.t + a, cue.t + b)
        before = _mean(x, t, cue.t - BEFORE_S, cue.t)
        change = None if during is None or before is None else during - before
        blocks.append(Block(cue.kind, cue.t - first, change))
    return FnirsScore(tuple(blocks))


def score_lines(result: FnirsScore) -> list[str]:
    lines = [f"fNIRS protocol score (fnirs {result.version}) - {EXPERIMENTAL}, relative units"]
    for kind, name in (("hold", "breath-hold"), ("arith", "arithmetic")):
        mine = [b for b in result.blocks if b.kind == kind]
        cells = "  ".join("-" if b.change_um is None else f"{b.change_um:+.2f}" for b in mine)
        up = sum(bool(b.expected) for b in mine)
        scored = sum(b.expected is not None for b in mine)
        lines.append(f"  {name:<12} HbO up in {up} of {scored} scored   change µM: {cells}")
    share = result.share
    if share is None:
        lines.append("RESULT        not scored: too little used signal")
        return lines
    verdict = "pass" if result.passed else "fail"
    scored = result.scored
    up = sum(bool(b.expected) for b in scored)
    lines.append(
        f"RESULT        {verdict} for this session: {up} of {len(scored)} blocks"
        f" ({100 * share:.0f}%) in the expected direction (70% needed)"
    )
    lines.append(
        "The gate needs 70% across 5 sessions on different days; the arithmetic direction on the"
        " forehead is not universal."
    )
    return lines
