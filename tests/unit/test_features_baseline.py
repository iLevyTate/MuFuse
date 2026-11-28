"""The personal baseline: rolling median and scaled MAD, z-scores against it (003 decision 8)."""

from __future__ import annotations

import pytest

from mufuse.features.baseline import Baseline


def test_no_z_score_until_enough_values() -> None:
    b = Baseline(window_s=100.0, min_n=5)
    zs = [b.add(float(v), t=float(t)) for t, v in enumerate([1, 2, 3, 4, 5])]
    assert zs == [None] * 5
    assert b.add(3.0, t=5.0) is not None


def test_the_z_score_is_against_the_values_before_it() -> None:
    b = Baseline(window_s=100.0, min_n=5)
    for t, v in enumerate([1.0, 2.0, 3.0, 4.0, 5.0]):
        b.add(v, t=float(t))
    # median 3, MAD 1, scaled 1.4826: 6 is (6 - 3) / 1.4826 above
    assert b.add(6.0, t=5.0) == pytest.approx(3 / 1.4826)


def test_old_values_leave_the_window() -> None:
    b = Baseline(window_s=10.0, min_n=3)
    for t in range(5):
        b.add(100.0 + t, t=float(t))
    for t in range(20, 25):
        b.add(float(t - 20), t=float(t))
    assert b.median == pytest.approx(2.0)  # only the values of the last 10 s are left


def test_a_series_that_never_changes_has_no_z_score() -> None:
    b = Baseline(window_s=100.0, min_n=3)
    for t in range(5):
        b.add(7.0, t=float(t))
    assert b.add(8.0, t=5.0) is None


def test_a_missing_value_is_skipped_not_counted() -> None:
    b = Baseline(window_s=100.0, min_n=2)
    assert b.add(None, t=0.0) is None
    assert b.count == 0
