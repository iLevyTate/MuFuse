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
    MAINS_SHARE,
    SENSORS,
    SensorView,
    grade_window,
    tip,
)
from mufuse.acquisition.signal_check import NOISY_UV

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


# One tip, for the sensor that needs it most ---------------------------------------------------


def _views(*shown: str) -> tuple[SensorView, ...]:
    return tuple(
        SensorView(name, state, None)  # type: ignore[arg-type]
        for name, state in zip(SENSORS, shown, strict=True)
    )


def test_the_tip_goes_to_the_worst_sensor() -> None:
    views = _views("noisy", "good", "good", "none")
    assert tip(views) == "TP10: push hair aside, wet the skin behind the ear"


def test_a_forehead_sensor_gets_the_forehead_tip() -> None:
    text = tip(_views("good", "none", "good", "good"))
    assert text is not None
    assert text.startswith("AF7: ")
    assert "forehead" in text


def test_a_noisy_sensor_gets_the_hold_still_tip() -> None:
    assert tip(_views("good", "good", "noisy", "good")) == "AF8: hold still, relax your jaw"


def test_settling_sensors_get_a_short_tip_and_all_good_none() -> None:
    assert tip(_views("settling", "settling", "good", "good")) == (
        "TP9: hold still while the signal settles"
    )
    assert tip(_views("good", "good", "good", "good")) is None
    assert tip(_views("waiting", "waiting", "waiting", "waiting")) is None
    assert tip(()) is None
