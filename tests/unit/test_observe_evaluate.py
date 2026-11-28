"""Does an interpreter beat chance on the wearer's own random check-ins? (006 decisions 6-8)"""

from __future__ import annotations

import numpy as np
import pytest

from mufuse.observe.evaluate import Point, auc, evaluate, next_look, verdict


def _points(n: int, effect: float, seed: int = 0, days: int = 10) -> list[Point]:
    """`n` random check-ins; the target is answered 30% of the time; scores shift by `effect`."""
    rng = np.random.default_rng(seed)
    out: list[Point] = []
    for i in range(n):
        target = bool(rng.random() < 0.3)
        score = float(rng.normal(effect if target else 0.0, 1.0))
        out.append(Point(day=i % days, score=score, target=target))
    return out


def test_auc_of_a_perfect_and_a_useless_score() -> None:
    assert auc([1.0, 2.0, 3.0, 4.0], [False, False, True, True]) == 1.0
    assert auc([1.0, 1.0, 1.0, 1.0], [False, True, False, True]) == 0.5
    assert auc([1.0], [True]) is None  # one class only


def test_a_planted_effect_is_found() -> None:
    result = evaluate(_points(150, effect=1.2), threshold=0.5, rng=np.random.default_rng(1))
    assert result.auc is not None
    assert result.auc > 0.7
    assert result.p is not None
    assert result.p < 0.01
    assert result.hit_rate is not None
    assert result.base_rate is not None
    assert result.hit_rate > result.base_rate


def test_no_effect_is_not_found() -> None:
    result = evaluate(_points(150, effect=0.0), threshold=0.5, rng=np.random.default_rng(1))
    assert result.p is not None
    assert result.p > 0.05


def test_looks_come_only_at_the_scheduled_counts() -> None:
    assert next_look(0, (50, 100, 150)) == 50
    assert next_look(49, (50, 100, 150)) == 50
    assert next_look(50, (50, 100, 150)) == 100
    assert next_look(170, (50, 100, 150)) == 200  # past the list, every 50 more


def test_between_looks_nothing_changes() -> None:
    pts = _points(70, effect=1.5)
    v = verdict(pts, state="shadow", last_look=50, looks=(50, 100), threshold=0.5, seed=1)
    assert (v.state, v.look) == ("shadow", 50)  # 70 answers: the next look is at 100


def test_promoted_at_a_look_when_it_beats_chance_then_demoted_when_it_stops() -> None:
    good = _points(100, effect=1.5)
    v = verdict(good, state="shadow", last_look=50, looks=(50, 100, 150), threshold=0.5, seed=1)
    assert (v.state, v.look) == ("promoted", 100)
    worse = good + _points(100, effect=-2.0, seed=7)  # the next 100 go the other way
    v2 = verdict(
        worse, state="promoted", last_look=100, looks=(50, 100, 150), threshold=0.5, seed=1
    )
    assert (v2.state, v2.look) == ("shadow", 200)  # past the list: every 50 more


def test_too_few_answers_is_not_yet_known() -> None:
    v = verdict(
        _points(20, effect=3.0), state="shadow", last_look=0, looks=(50,), threshold=0.5, seed=1
    )
    assert v.state == "shadow"
    assert v.look == 0
    assert v.evaluation.n == 20


def test_the_shuffle_keeps_each_day_together() -> None:
    # Every target on day 0 and high scores on day 0 only: a day effect, not a score effect.
    pts = [Point(day=0, score=5.0, target=True) for _ in range(10)]
    pts += [Point(day=d, score=0.0, target=False) for d in range(1, 10) for _ in range(10)]
    result = evaluate(pts, threshold=0.5, rng=np.random.default_rng(0))
    assert result.auc == pytest.approx(1.0)
    assert result.p is not None
    assert result.p > 0.05  # shuffling within days cannot break it, so it is not evidence
