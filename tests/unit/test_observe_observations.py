"""Neutral observations: a series away from its baseline for long enough (006 decision 1)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from mufuse.features.engine import FeatureFrame
from mufuse.observe.observations import ObservationDetector, ObservationEvent


def _frame(t: float, **z: float | None) -> FeatureFrame:
    zs: Mapping[str, float | None] = {"blinks_per_min": None, "alpha_share": None} | z
    return FeatureFrame(t=t, values={}, z=zs)


def _feed(
    d: ObservationDetector, zs: Sequence[float | None], series: str = "blinks_per_min"
) -> list[ObservationEvent]:
    found: list[ObservationEvent] = []
    for i, z in enumerate(zs):
        found += d.add(_frame(float(i), **{series: z}))
    return found


def test_a_short_spike_is_not_an_observation() -> None:
    assert _feed(ObservationDetector(), [0.0] * 20 + [3.0] * 5 + [0.0] * 20) == []


def test_a_held_shift_starts_one_observation_after_the_smoothing() -> None:
    found = _feed(ObservationDetector(), [0.0] * 20 + [3.0] * 30)
    (started,) = [e for e in found if e.kind == "start"]
    assert started.series == "blinks_per_min"
    assert started.direction == "higher"
    assert 27.0 <= started.t <= 30.0  # half of the 15 s window must be above 2 first


def test_it_ends_only_when_the_signal_falls_back_under_1() -> None:
    d = ObservationDetector()
    found = _feed(d, [0.0] * 20 + [3.0] * 30 + [1.5] * 30 + [0.0] * 30)
    kinds = [e.kind for e in found]
    assert kinds == ["start", "end"]
    end = found[-1]
    assert end.t > 80.0  # 1.5 is between the two limits: still the same observation


def test_lower_is_named_lower() -> None:
    found = _feed(ObservationDetector(), [0.0] * 20 + [-2.5] * 30, series="alpha_share")
    assert found[0].direction == "lower"
    assert found[0].series == "alpha_share"


def test_missing_values_do_not_start_or_end_anything() -> None:
    d = ObservationDetector()
    assert _feed(d, [None] * 40) == []
    assert d.active == {}


def test_the_text_is_neutral_and_about_the_signal() -> None:
    (started, *_) = _feed(ObservationDetector(), [0.0] * 20 + [3.0] * 30)
    assert started.text == "blink rate higher than usual"
