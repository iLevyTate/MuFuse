"""Whether an interpreter beats chance on the wearer's own random check-ins (006 decisions 6-8).

Only random check-ins count: a check-in asked because a signal shifted would flatter any detector
of that shift. The AUC says how well the score orders target answers above the others; its
p-value comes from shuffling the answers within each day, so a day that was simply different
cannot pass for an effect. Judgement happens at fixed counts only (the looks): judging after every
answer would, sooner or later, find an effect that is not there.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

State = Literal["shadow", "promoted"]
PERMUTATIONS = 2000
ALPHA = 0.05
LOOK_STEP = 50


@dataclass(frozen=True)
class Point:
    """One answered random check-in: its day, the interpreter's score, and whether the answer was
    one of the interpreter's target answers."""

    day: int
    score: float
    target: bool


@dataclass(frozen=True)
class Evaluation:
    n: int
    base_rate: float | None  # share of target answers among all points
    fired: int
    hit_rate: float | None  # share of target answers where the score reached the threshold
    auc: float | None
    p: float | None

    @property
    def beats_chance(self) -> bool:
        return (
            self.auc is not None
            and self.p is not None
            and self.hit_rate is not None
            and self.base_rate is not None
            and self.auc > 0.5
            and self.p < ALPHA
            and self.hit_rate > self.base_rate
        )


@dataclass(frozen=True)
class Verdict:
    state: State
    look: int  # the last look judged
    evaluation: Evaluation


def auc(scores: Sequence[float] | np.ndarray, labels: Sequence[bool] | np.ndarray) -> float | None:
    """P(a target scores above a non-target), ties counting half; None with one class."""
    s, y = np.asarray(scores, dtype=np.float64), np.asarray(labels, dtype=bool)
    pos, neg = s[y], s[~y]
    if pos.size == 0 or neg.size == 0:
        return None
    above = (pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()
    return float(above) / (pos.size * neg.size)


def evaluate(points: Sequence[Point], *, threshold: float, rng: np.random.Generator) -> Evaluation:
    n = len(points)
    if n == 0:
        return Evaluation(0, None, 0, None, None, None)
    scores = np.array([p.score for p in points])
    labels = np.array([p.target for p in points])
    days = np.array([p.day for p in points])
    fired = scores >= threshold
    found = auc(scores, labels)
    p = None
    if found is not None:
        beaten = 0
        groups = [np.flatnonzero(days == d) for d in np.unique(days)]
        shuffled = labels.copy()
        for _ in range(PERMUTATIONS):
            for g in groups:
                shuffled[g] = rng.permutation(labels[g])
            if (auc(scores, shuffled) or 0.5) >= found:
                beaten += 1
        p = (beaten + 1) / (PERMUTATIONS + 1)
    return Evaluation(
        n=n,
        base_rate=float(labels.mean()),
        fired=int(fired.sum()),
        hit_rate=float(labels[fired].mean()) if fired.any() else None,
        auc=found,
        p=p,
    )


def next_look(n: int, looks: Sequence[int]) -> int:
    """The next count at which the interpreter is judged; past the list, every 50 more."""
    for look in looks:
        if look > n:
            return look
    last = looks[-1] if looks else 0
    return last + LOOK_STEP * ((n - last) // LOOK_STEP + 1)


def _reached(n: int, looks: Sequence[int]) -> int:
    """The largest look at or below `n` (0 for none)."""
    reached, look = 0, next_look(0, looks)
    while look <= n:
        reached, look = look, next_look(look, looks)
    return reached


def verdict(
    points: Sequence[Point],
    *,
    state: State,
    last_look: int,
    looks: Sequence[int],
    threshold: float,
    seed: int = 0,
) -> Verdict:
    """The state after any look that `points` has newly reached; unchanged between looks."""
    evaluation = evaluate(points, threshold=threshold, rng=np.random.default_rng(seed))
    look = _reached(len(points), looks)
    if look <= last_look:
        return Verdict(state, last_look, evaluation)
    new: State = "promoted" if evaluation.beats_chance else "shadow"
    return Verdict(new, look, evaluation)
