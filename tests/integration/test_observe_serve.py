"""006 inside `mufuse serve`: observations offer shift check-ins, scores are kept in shadow, and
insights appear only when promoted or switched on (006 decisions 2, 5, 9)."""

from __future__ import annotations

import json
from pathlib import Path

from mufuse.features.engine import FeatureFrame
from mufuse.observe.interpreters import EARLY_TAG
from mufuse.observe.ledger import set_early
from tests.integration.test_companion_serve import EXAMPLES, Caught, _engine, _run, _same_shape


def _feed(engine, clock, seconds: int, **z: float) -> None:
    for _ in range(seconds):
        clock.advance(1.0)
        engine._on_frame(FeatureFrame(t=clock.now, values={}, z=dict(z)))  # pyright: ignore[reportPrivateUsage]


def test_a_held_shift_is_published_as_an_observation(tmp_path: Path) -> None:
    engine, clock, caught = _engine(tmp_path, record=False)
    _feed(engine, clock, 20, blinks_per_min=0.0)
    _feed(engine, clock, 20, blinks_per_min=3.0)
    (obs,) = caught.of("observation")
    assert (obs["state"], obs["series"], obs["direction"]) == ("start", "blinks_per_min", "higher")
    assert obs["text"] == "blink rate higher than usual"
    engine.stop()


def test_every_check_in_stores_every_interpreters_score(tmp_path: Path) -> None:
    engine, clock, _ = _engine(tmp_path, record=False)
    _run(engine, clock, 3.0)
    _feed(engine, clock, 40, blinks_per_min=2.0, alpha_share=1.0)
    engine.command({"type": "checkin"})
    rows = engine.store._db.execute("SELECT interpreter, score, fired FROM scores").fetchall()  # pyright: ignore[reportPrivateUsage]
    assert rows == [("attention_drift", 1.5, 1)]
    engine.stop()


def test_no_insight_in_shadow_mode(tmp_path: Path) -> None:
    engine, clock, caught = _engine(tmp_path, record=False)
    _feed(engine, clock, 40, blinks_per_min=2.0, alpha_share=2.0)
    assert caught.of("insight") == []
    engine.stop()


def test_with_early_feedback_on_an_insight_carries_the_tag_once_per_15_minutes(
    tmp_path: Path,
) -> None:
    engine, clock, caught = _engine(tmp_path, record=False)
    set_early(engine.store, "attention_drift", True)
    _feed(engine, clock, 40, blinks_per_min=2.0, alpha_share=2.0)
    (insight,) = caught.of("insight")
    assert insight["early"] is True
    assert insight["text"].endswith(f"({EARLY_TAG})")
    assert "you are" not in insight["text"].lower()
    _feed(engine, clock, 60, blinks_per_min=2.0, alpha_share=2.0)
    assert len(caught.of("insight")) == 1
    # A check-in soon after the insight is scored but kept out of the evaluation.
    engine.command({"type": "checkin"})
    (after,) = engine.store._db.execute("SELECT after_insight FROM scores").fetchone()  # pyright: ignore[reportPrivateUsage]
    assert after == 1
    engine.stop()


def test_observation_and_insight_have_the_shape_of_their_examples(tmp_path: Path) -> None:
    engine, clock, caught = _engine(tmp_path, record=False)
    set_early(engine.store, "attention_drift", True)
    _feed(engine, clock, 20, blinks_per_min=0.0, alpha_share=0.0)
    _feed(engine, clock, 40, blinks_per_min=3.0, alpha_share=3.0)
    engine.stop()
    for kind in ("observation", "insight"):
        example = json.loads((EXAMPLES / f"{kind}.json").read_text(encoding="utf-8"))
        _same_shape(caught.of(kind)[0], example)


__all__ = ["Caught"]
