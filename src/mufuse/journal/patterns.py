"""Weekly patterns, counted in code (008 decisions 1-3; ROADMAP gate).

A pattern says how often an answer came in a situation, against how often it came at all, on the
wearer's own random check-ins. It always shows n, the effect in percentage points and the word
"hypothesis": co-occurrence in a few answers is a lead to look at, not a finding.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from mufuse.companion.store import CheckIn, Store
from mufuse.observe.observations import NAMES

MIN_N = 3
WITHIN_S = 10 * 60.0  # a check-in this soon after an observation started counts as "after" it
MAX_SHOWN = 10


@dataclass(frozen=True)
class Pattern:
    when: str  # "after blink rate higher" | "in meetings"
    answer: str
    hits: int
    n: int
    base: float  # share of this answer over all random check-ins of the period
    label: str = "hypothesis"

    @property
    def share(self) -> float:
        return self.hits / self.n

    @property
    def effect_pts(self) -> float:
        return 100.0 * (self.share - self.base)


def _patterns(when: str, group: Sequence[CheckIn], base: dict[str, float]) -> list[Pattern]:
    if len(group) < MIN_N:
        return []
    counts = Counter(c.answer for c in group if c.answer is not None)
    return [
        Pattern(when, answer, hits, len(group), base[answer]) for answer, hits in counts.items()
    ]


def find(store: Store, *, since: float, until: float = 1e18) -> list[Pattern]:
    """The patterns of a period, largest effect first; only from random answered check-ins."""
    random = [
        c
        for c in store.checkins()
        if c.source == "random" and c.answer is not None and since <= c.asked_t <= until
    ]
    if not random:
        return []
    totals = Counter(c.answer for c in random if c.answer is not None)
    base = {answer: count / len(random) for answer, count in totals.items()}
    found: list[Pattern] = []
    kinds: dict[tuple[str, str], list[float]] = {}
    for o in store.observations(since=since - WITHIN_S):
        kinds.setdefault((o.series, o.direction), []).append(o.start)
    for (series, direction), starts in sorted(kinds.items()):
        after = [c for c in random if any(0 <= c.asked_t - s <= WITHIN_S for s in starts)]
        found += _patterns(f"after {NAMES.get(series, series)} {direction}", after, base)
    windows: dict[str, list[tuple[float, float]]] = {}
    for w in store.context(since=since, until=until):
        windows.setdefault(w.tag, []).append((w.start, w.end))
    for tag, spans in sorted(windows.items()):
        inside = [c for c in random if any(a <= c.asked_t <= b for a, b in spans)]
        found += _patterns(f"in {tag}s", inside, base)
    found.sort(key=lambda p: (-p.effect_pts, -p.n, p.when, p.answer))
    return [p for p in found if p.effect_pts > 0][:MAX_SHOWN]


def pattern_line(p: Pattern) -> str:
    return (
        f"{p.when}: '{p.answer}' {p.hits} of {p.n} times ({100 * p.share:.0f}%) against"
        f" {100 * p.base:.0f}% overall, {p.effect_pts:+.0f} points, n={p.n} · {p.label}"
    )


def pattern_lines(patterns: Sequence[Pattern]) -> list[str]:
    lines = [
        "Patterns in your random check-ins. Many are compared, so some will be chance;"
        " each is a hypothesis to look at, not a finding."
    ]
    if not patterns:
        lines.append(f"No pattern has enough random check-ins yet (at least {MIN_N}).")
    lines += [pattern_line(p) for p in patterns]
    return lines
