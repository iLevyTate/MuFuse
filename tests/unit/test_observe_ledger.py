"""Interpreter standing kept in the store: scores, looks, early feedback (006 decisions 5-9)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from mufuse.companion.store import DEFAULT_ANSWERS, Store
from mufuse.observe.interpreters import load_all
from mufuse.observe.ledger import counts, review, set_early

DAY = 86_400.0


def _fill(
    store: Store, n: int, effect: float, *, source: str = "random", after_insight: bool = False
) -> None:
    (drift,) = load_all()
    m = drift.manifest
    rng = np.random.default_rng(0)
    session = store.start_session(t=0.0)
    for i in range(n):
        target = bool(rng.random() < 0.3)
        score = float(rng.normal(effect if target else 0.0, 1.0))
        t = 1_800_000_000.0 + (i % 10) * DAY + i
        c = store.ask(session, t=t, source=source, order=DEFAULT_ANSWERS)  # type: ignore[arg-type]
        store.answer(c, t=t + 3, answer=m.target[0] if target else "on task")
        store.add_score(
            c,
            interpreter=m.id,
            version=m.version,
            score=score,
            fired=score >= m.threshold,
            after_insight=after_insight,
        )


def test_a_new_interpreter_is_in_shadow_with_early_feedback_off(tmp_path: Path) -> None:
    store = Store(tmp_path / "db")
    (drift,) = load_all()
    standing = review(store, drift)
    assert (standing.state.state, standing.state.early, standing.next_look) == ("shadow", False, 50)


def test_it_is_promoted_at_its_look_when_it_beats_chance(tmp_path: Path) -> None:
    store = Store(tmp_path / "db")
    _fill(store, 50, effect=2.0)
    (drift,) = load_all()
    standing = review(store, drift)
    assert (standing.state.state, standing.state.last_look) == ("promoted", 50)
    assert store.interpreter("attention_drift").state == "promoted"  # kept


def test_only_random_check_ins_count(tmp_path: Path) -> None:
    store = Store(tmp_path / "db")
    _fill(store, 60, effect=2.0, source="shift")
    _fill(store, 60, effect=2.0, source="self")
    (drift,) = load_all()
    assert review(store, drift).verdict.evaluation.n == 0


def test_check_ins_right_after_an_insight_are_left_out(tmp_path: Path) -> None:
    store = Store(tmp_path / "db")
    _fill(store, 60, effect=2.0, after_insight=True)
    (drift,) = load_all()
    assert review(store, drift).verdict.evaluation.n == 0


def test_early_feedback_switches_without_touching_the_evaluation(tmp_path: Path) -> None:
    store = Store(tmp_path / "db")
    _fill(store, 20, effect=2.0)
    (drift,) = load_all()
    before = review(store, drift)
    set_early(store, "attention_drift", True)
    after = review(store, drift)
    assert after.state.early is True
    assert after.verdict.evaluation == before.verdict.evaluation
    set_early(store, "attention_drift", False)
    assert store.interpreter("attention_drift").early is False


def test_counts_are_hits_of_fired(tmp_path: Path) -> None:
    store = Store(tmp_path / "db")
    _fill(store, 40, effect=3.0)
    (drift,) = load_all()
    hits, fired = counts(store, drift)
    assert 0 < hits <= fired
