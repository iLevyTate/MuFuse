"""When to ask "What's on your mind?" (005 decisions 2-5).

Random moments come after an exponential wait (15 minutes plus, on average, 10 more), so they are
not predictable from the clock. A check-in asked because a signal shifted is only allowed while
the random share of asked check-ins stays at or above 30%: without random questions there is no
way to tell later whether a detector does better than chance. Holds no clock of its own.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from mufuse.companion.store import Source

MEAN_WAIT_S = 25 * 60.0
SPACING_S = 15 * 60.0
MIN_RANDOM_SHARE = 0.3
SNOOZE_S = 60 * 60.0
EXPIRE_S = 120.0
OWN_WORDS = "own words"


@dataclass(frozen=True)
class Conditions:
    """What the engine knows right now that can make it a quiet time."""

    signal_good: bool  # at least one forehead sensor is good
    moving: bool
    focus: bool  # a do-not-disturb focus block


CALM = Conditions(signal_good=True, moving=False, focus=False)


@dataclass(frozen=True)
class Ask:
    t: float
    source: Source
    shuffle: tuple[int, ...]  # how this check-in orders the answer list

    def order(self, answers: Sequence[str]) -> tuple[str, ...]:
        """The answers in this check-in's order, with "own words" always last."""
        rest = [a for a in answers if a != OWN_WORDS]
        ranked = sorted(
            range(len(rest)), key=lambda i: self.shuffle[i % len(self.shuffle)] + i * 1e-9
        )
        tail = (OWN_WORDS,) if OWN_WORDS in answers else ()
        return (*(rest[i] for i in ranked), *tail)


class Scheduler:
    def __init__(
        self,
        rng: np.random.Generator,
        *,
        start_t: float,
        mean_wait_s: float = MEAN_WAIT_S,
        spacing_s: float = SPACING_S,
        min_random_share: float = MIN_RANDOM_SHARE,
        snooze_s: float = SNOOZE_S,
        expire_s: float = EXPIRE_S,
    ) -> None:
        self._rng = rng
        # Orders come from their own generator: opening a check-in never moves the random moments.
        self._order_rng = np.random.default_rng(int(rng.integers(2**62)))
        self._mean, self._spacing = mean_wait_s, spacing_s
        self._min_share, self._snooze_s, self._expire_s = min_random_share, snooze_s, expire_s
        self._next_random = start_t + self._wait()
        self._last_asked = start_t  # nothing is asked in the first spacing of a session
        self._snoozed_until = -np.inf
        self._open: Ask | None = None
        self.asked = {"random": 0, "shift": 0}

    def _wait(self) -> float:
        return self._spacing + float(self._rng.exponential(self._mean - self._spacing))

    def _shuffle(self) -> tuple[int, ...]:
        return tuple(int(i) for i in self._order_rng.permutation(32))

    @property
    def open(self) -> Ask | None:
        return self._open

    def _quiet(self, t: float, cond: Conditions) -> bool:
        return (
            not cond.signal_good
            or cond.moving
            or cond.focus
            or t < self._snoozed_until
            or t < self._last_asked + self._spacing
            or self._open is not None
        )

    def tick(self, t: float, cond: Conditions) -> Ask | None:
        """A random check-in, if its moment has come and it is not a quiet time."""
        if t < self._next_random:
            return None
        self._next_random = t + self._wait()  # a skipped moment is gone, not queued
        if self._quiet(t, cond):
            return None
        return self._ask(t, "random")

    def shift(self, t: float, cond: Conditions) -> Ask | None:
        """A check-in because a signal shifted (006), if the spacing and the random share allow."""
        random, shift = self.asked["random"], self.asked["shift"]
        if self._quiet(t, cond) or random < self._min_share * (random + shift + 1):
            return None
        return self._ask(t, "shift")

    def self_checkin(self, t: float) -> Ask:
        """The wearer opened one: always allowed, and it leaves the spacing as it was."""
        self._open = Ask(t, "self", self._shuffle())
        return self._open

    def _ask(self, t: float, source: Source) -> Ask:
        self.asked[source] += 1
        self._last_asked = t
        self._open = Ask(t, source, self._shuffle())
        return self._open

    def close(self, t: float) -> None:
        """The open check-in was answered or has expired."""
        self._open = None

    def expired(self, t: float) -> bool:
        return self._open is not None and t >= self._open.t + self._expire_s

    def snoozed(self, t: float) -> bool:
        return t < self._snoozed_until

    def snooze(self, t: float) -> None:
        self._snoozed_until = t + self._snooze_s
