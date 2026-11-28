"""Interpreter manifests, the registry and attention_drift (006 decisions 3-5, 9-10)."""

from __future__ import annotations

import pytest

from mufuse.features.engine import FeatureFrame
from mufuse.observe.interpreters import EARLY_TAG, REGISTRY, AttentionDrift, Manifest, load_all

GOOD = """
id = "x"
version = 1
title = "X"
tier = "speculative"
target = ["daydreaming"]
needs = ["blinks_per_min", "alpha_share"]
needs_share = 0.5
window_s = 30.0
threshold = 1.0
looks = [50, 100]
phrasing = "Blink rate is up{counts}. What was going on?"
"""


def _frames(n: int, blinks: float | None, alpha: float | None) -> list[FeatureFrame]:
    return [
        FeatureFrame(t=float(i), values={}, z={"blinks_per_min": blinks, "alpha_share": alpha})
        for i in range(n)
    ]


def test_the_shipped_interpreters_load_and_start_speculative() -> None:
    (drift,) = load_all()
    assert set(REGISTRY) == {"attention_drift"}
    m = drift.manifest
    assert (m.id, m.tier) == ("attention_drift", "speculative")
    assert m.window_s >= 15.0
    assert m.looks == (50, 100, 150)


def test_attention_drift_scores_the_mean_of_both_z_scores() -> None:
    drift = AttentionDrift(Manifest.parse(GOOD))
    assert drift.score(_frames(30, 2.0, 1.0)) == pytest.approx(1.5)


def test_too_little_of_a_needed_series_gives_no_score() -> None:
    drift = AttentionDrift(Manifest.parse(GOOD))
    frames = _frames(10, 2.0, 1.0) + _frames(20, 2.0, None)
    assert drift.score(frames) is None
    assert drift.score([]) is None


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ('tier = "speculative"', 'tier = "certain"'),
        ("window_s = 30.0", "window_s = 5.0"),
        ("looks = [50, 100]", "looks = [100, 50]"),
        (
            'phrasing = "Blink rate is up{counts}. What was going on?"',
            'phrasing = "You are bored{counts}."',
        ),
    ],
)
def test_a_manifest_that_breaks_a_rule_is_refused(change: str, error: str) -> None:
    with pytest.raises(ValueError, match=r"tier|window_s|looks|phrasing"):
        Manifest.parse(GOOD.replace(change, error))


def test_the_phrasing_gets_counts_from_code_and_the_tag_when_early() -> None:
    m = Manifest.parse(GOOD)
    assert m.say(early=False) == "Blink rate is up. What was going on?"
    said = m.say(hits=6, fired=9, early=True)
    assert "daydreaming 6 of 9 times" in said
    assert said.endswith(f"({EARLY_TAG})")
