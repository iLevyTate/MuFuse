"""Contact grading for the live view, on windows shaped like the 2026-11-26 sitting (issue #13).

Numbers from that sitting, per 1 s window of raw (un-centred) EEG: good contact read 8-40 µV of
spread, and 80-98% of its power above 1 Hz was mains hum all the same; a sensor not touching the
skin read 100-550 µV with 85-100% at 60 Hz; a touching but moving one read high with under 25%
at 60 Hz; a sensor off the skin could also sit at full scale (±725 µV) for most of a window.
Every window here also carries the 1-3 µV period-12 pattern (21.3, 42.7, 64 Hz lines) that the
Athena shows in all presets.
"""

from __future__ import annotations

import numpy as np
import pytest

from mufuse.acquisition.contact import (
    HOLD_S,
    MAINS_SHARE,
    ContactTracker,
    grade_window,
    tip,
)
from mufuse.acquisition.signal_check import NOISY_UV
from tests.conftest import FakeClock

FS = 256
T = np.arange(FS) / FS
RNG = np.random.default_rng(7)


def _pattern() -> np.ndarray:
    """The Athena's period-12 dip: one sample in twelve sits about 3 µV low."""
    return np.where(np.arange(FS) % 12 == 0, -3.0, 0.0)


def _good(offset: float = 40.0, noise: float = 9.0, hum: float = 30.0) -> np.ndarray:
    return offset + noise * RNG.standard_normal(FS) + hum * np.sin(2 * np.pi * 60 * T) + _pattern()


def _no_contact(hz: float = 60.0, amplitude: float = 300.0) -> np.ndarray:
    return amplitude * np.sin(2 * np.pi * hz * T) + 5 * RNG.standard_normal(FS) + _pattern()


def _moving() -> np.ndarray:
    drift = 160 * np.sin(2 * np.pi * 1.5 * T) + 90 * np.sin(2 * np.pi * 4 * T + 1)
    return drift + 60 * RNG.standard_normal(FS) + 20 * np.sin(2 * np.pi * 60 * T)


# One window ------------------------------------------------------------------------------------


def test_good_contact_is_good_although_most_of_its_power_is_mains() -> None:
    reading = grade_window(_good())
    assert reading is not None
    assert reading.grade == "good"
    assert reading.mains_share > 0.8  # hum alone does not mean no contact
    assert 8 <= reading.spread_uv <= 40


@pytest.mark.parametrize("hz", [50.0, 60.0])
def test_loud_and_mostly_mains_is_no_contact(hz: float) -> None:
    reading = grade_window(_no_contact(hz))
    assert reading is not None
    assert (reading.grade, reading.why) == ("none", "hum")
    assert reading.mains_share >= 0.85
    assert reading.spread_uv > 100


def test_loud_without_mains_is_noisy_contact() -> None:
    reading = grade_window(_moving())
    assert reading is not None
    assert (reading.grade, reading.why) == ("noisy", "loud")
    assert reading.mains_share < 0.25
    assert reading.spread_uv > NOISY_UV


def test_a_window_mostly_at_full_scale_is_no_contact() -> None:
    x = _good()
    x[40:120] = 725.0  # about 30% of the window at the rail, as an off-skin sensor reads
    reading = grade_window(x)
    assert reading is not None
    assert (reading.grade, reading.why) == ("none", "railed")


def test_the_rail_is_judged_before_centring() -> None:
    # A steady offset near the rail is still the rail: centring would hide it.
    reading = grade_window(718.0 + 2 * RNG.standard_normal(FS))
    assert reading is not None
    assert reading.why == "railed"


def test_a_few_samples_at_the_rail_do_not_count() -> None:
    x = _good()
    x[:20] = 725.0  # under 10%
    reading = grade_window(x)
    assert reading is not None
    assert reading.grade == "good"


def test_a_flat_channel_is_no_contact() -> None:
    reading = grade_window(np.full(FS, 12.0))
    assert reading is not None
    assert (reading.grade, reading.why) == ("none", "flat")


def test_a_floating_input_with_the_period_12_dips_is_no_contact() -> None:
    # The unconnected input of the public muse-rs capture, which the simulator copies: quiet by
    # robust spread, loud by plain std, nearly all of it on the period-12 lines.
    dips = np.tile([-75.0, -675.0, -460.0, *[0.0] * 9], FS // 12 + 1)[:FS]
    reading = grade_window(115.0 + dips + 25 * RNG.standard_normal(FS))
    assert reading is not None
    assert reading.spread_uv <= NOISY_UV
    assert (reading.grade, reading.why) == ("none", "floating")


def test_the_athena_interference_lines_are_not_mains() -> None:
    # Loud, and nearly all of it on the 64 Hz and 21.3 Hz lines next to the mains bands.
    x = 250 * np.sin(2 * np.pi * 64 * T) + 200 * np.sin(2 * np.pi * (FS / 12) * T)
    x += 120 * RNG.standard_normal(FS)
    reading = grade_window(x)
    assert reading is not None
    assert reading.mains_share < MAINS_SHARE
    assert reading.grade == "noisy"


def test_too_little_data_is_no_reading() -> None:
    assert grade_window(_good()[:60]) is None
    assert grade_window(np.full(FS, np.nan)) is None


# Over time: hold before green ------------------------------------------------------------------


def _window(*sensors: np.ndarray) -> np.ndarray:
    return np.column_stack([*sensors, np.zeros((FS, 4))])  # the AUX rows are never looked at


def test_a_sensor_turns_green_only_after_three_good_seconds(clock: FakeClock) -> None:
    tracker = ContactTracker(clock=clock)
    shown: list[tuple[str, int]] = []
    for _ in range(8):
        view = tracker.update(_window(_good(), _good(), _good(), _good()))[0]
        shown.append((view.shown, view.settle_left_s))
        clock.advance(0.5)
    assert shown[:6] == [
        ("settling", 3),
        ("settling", 3),
        ("settling", 2),
        ("settling", 2),
        ("settling", 1),
        ("settling", 1),
    ]
    assert shown[6:] == [("good", 0), ("good", 0)]
    assert HOLD_S == 3.0


def test_a_worse_grade_shows_at_once_and_green_must_be_earned_again(clock: FakeClock) -> None:
    tracker = ContactTracker(clock=clock)
    for _ in range(7):
        tracker.update(_window(_good(), _good(), _good(), _good()))
        clock.advance(0.5)
    views = tracker.update(_window(_no_contact(), _moving(), _good(), _good()))
    assert [v.shown for v in views] == ["none", "noisy", "good", "good"]
    clock.advance(1.0)
    views = tracker.update(_window(_good(), _good(), _good(), _good()))
    assert [v.shown for v in views] == ["settling", "settling", "good", "good"]
    assert views[0].settle_left_s == 3


def test_no_data_is_waiting(clock: FakeClock) -> None:
    views = ContactTracker(clock=clock).update(np.empty((0, 8)))
    assert [(v.name, v.shown, v.reading) for v in views] == [
        ("TP9", "waiting", None),
        ("AF7", "waiting", None),
        ("AF8", "waiting", None),
        ("TP10", "waiting", None),
    ]


def test_waiting_forgets_the_good_streak(clock: FakeClock) -> None:
    tracker = ContactTracker(clock=clock)
    for _ in range(7):
        tracker.update(_window(_good(), _good(), _good(), _good()))
        clock.advance(0.5)
    tracker.update(np.empty((0, 8)))  # the link dropped
    clock.advance(0.5)
    assert tracker.update(_window(_good(), _good(), _good(), _good()))[0].shown == "settling"


# One tip, for the sensor that needs it most ---------------------------------------------------


def _views(clock: FakeClock, *sensors: np.ndarray, settle: bool = False):  # type: ignore[no-untyped-def]
    tracker = ContactTracker(clock=clock)
    if not settle:
        for _ in range(7):
            tracker.update(_window(_good(), _good(), _good(), _good()))
            clock.advance(0.5)
    return tracker.update(_window(*sensors))


def test_the_tip_goes_to_the_worst_sensor(clock: FakeClock) -> None:
    views = _views(clock, _moving(), _good(), _good(), _no_contact())
    assert tip(views) == "TP10: push hair aside, wet the skin behind the ear"


def test_a_forehead_sensor_gets_the_forehead_tip(clock: FakeClock) -> None:
    views = _views(clock, _good(), _no_contact(), _good(), _good())
    text = tip(views)
    assert text is not None
    assert text.startswith("AF7: ")
    assert "forehead" in text


def test_a_noisy_sensor_gets_the_hold_still_tip(clock: FakeClock) -> None:
    assert tip(_views(clock, _good(), _good(), _moving(), _good())) == (
        "AF8: hold still, relax your jaw"
    )


def test_settling_sensors_get_a_short_tip_and_all_good_none(clock: FakeClock) -> None:
    assert tip(_views(clock, _good(), _good(), _good(), _good(), settle=True)) == (
        "TP9: hold still while the signal settles"
    )
    assert tip(_views(clock, _good(), _good(), _good(), _good())) is None
    assert tip(ContactTracker(clock=clock).update(np.empty((0, 8)))) is None
