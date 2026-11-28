"""When to ask (005 decisions 2-5): random moments, spacing, quiet times, the 30% random share."""

from __future__ import annotations

import numpy as np
import pytest

from mufuse.companion.scheduler import CALM, Conditions, Scheduler

MIN = 60.0


def _scheduler(seed: int = 0, **kw: float) -> Scheduler:
    return Scheduler(np.random.default_rng(seed), start_t=0.0, **kw)


def _run(
    s: Scheduler, hours: float, cond: Conditions = CALM, answer_after: float = 10.0
) -> list[float]:
    asked: list[float] = []
    t = 0.0
    while t < hours * 3600:
        ask = s.tick(t, cond)
        if ask is not None:
            asked.append(t)
            s.close(t + answer_after)
        t += 1.0
    return asked


def test_random_check_ins_average_one_every_25_minutes_and_never_closer_than_15() -> None:
    asked = _run(_scheduler(), hours=40)
    gaps = np.diff(asked)
    assert gaps.min() >= 15 * MIN
    assert np.mean(gaps) == pytest.approx(25 * MIN, rel=0.15)


def test_no_check_in_in_the_first_15_minutes() -> None:
    assert _run(_scheduler(), hours=4)[0] >= 15 * MIN


@pytest.mark.parametrize(
    "cond",
    [
        Conditions(signal_good=False, moving=False, focus=False),
        Conditions(signal_good=True, moving=True, focus=False),
        Conditions(signal_good=True, moving=False, focus=True),
    ],
)
def test_quiet_times_skip_random_moments(cond: Conditions) -> None:
    assert _run(_scheduler(), hours=3, cond=cond) == []


def test_snooze_holds_every_asked_check_in_for_an_hour() -> None:
    s = _scheduler()
    s.snooze(0.0)
    assert all(t >= 60 * MIN for t in _run(s, hours=3))


def test_a_shift_waits_for_a_random_one_first_so_the_share_holds() -> None:
    s = _scheduler()
    assert s.shift(20 * MIN, CALM) is None  # nothing random yet: a shift would make it 0% random


def test_the_random_share_never_falls_under_30_percent() -> None:
    s = _scheduler(seed=3)
    sources: list[str] = []
    for t in np.arange(0.0, 30 * 3600.0, 1.0):
        ask = s.tick(float(t), CALM)
        if ask is None and int(t) % 60 == 0:
            ask = s.shift(float(t), CALM)  # 006 would offer a shift as often as once a minute
        if ask is not None:
            sources.append(ask.source)
            s.close(float(t) + 5.0)
            share = sources.count("random") / len(sources)
            assert share >= 0.3
    assert "shift" in sources
    assert sources.count("random") / len(sources) >= 0.3


def test_a_self_check_in_is_always_allowed_and_keeps_the_spacing() -> None:
    s = _scheduler()
    s.snooze(0.0)
    ask = s.self_checkin(5 * MIN)
    assert ask.source == "self"
    s.close(5 * MIN + 10)
    assert _run(_scheduler(), hours=1) == _run_after_self(hours=1)


def _run_after_self(hours: float) -> list[float]:
    s = _scheduler()
    s.self_checkin(1.0)
    s.close(2.0)
    return _run(s, hours=hours)


def test_an_open_check_in_expires_after_two_minutes() -> None:
    s = _scheduler()
    s.self_checkin(0.0)
    assert not s.expired(119.0)
    assert s.expired(120.0)


def test_the_answers_come_in_a_new_order_with_own_words_last() -> None:
    s = _scheduler()
    answers = ("a", "b", "c", "d", "e", "own words")
    orders = {s.self_checkin(float(i)).order(answers) for i in range(20)}
    assert len(orders) > 5
    assert all(o[-1] == "own words" and sorted(o) == sorted(answers) for o in orders)
