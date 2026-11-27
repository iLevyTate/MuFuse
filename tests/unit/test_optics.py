from __future__ import annotations

import numpy as np

from mufuse.acquisition.optics import OPTICS_FULL_SCALE, detector_grades, too_much_light

ON_HEAD = np.array(
    [
        *(239_000, 212_000, 620, 370, 340_800, 341_100, 340_600, 340_900),
        *(192_000, 206_000, 39_600, 35_600, 190_000, 172_000, 21_600, 17_900),
    ],
    dtype=np.float64,
)


def test_full_scale_is_the_20_bit_ceiling() -> None:
    assert OPTICS_FULL_SCALE == 2**20 - 1 == 1_048_575


def test_on_the_head_the_frames_hold_data() -> None:
    assert not too_much_light(np.tile(ON_HEAD, (3, 1))).any()


def test_an_ambient_row_at_full_scale_is_too_much_light() -> None:
    frames = np.tile(ON_HEAD, (3, 1))
    frames[1, 5] = OPTICS_FULL_SCALE
    assert too_much_light(frames).tolist() == [False, True, False]


def test_every_led_row_at_zero_is_too_much_light() -> None:
    # What a bright lamp did in a real F1 phase: the headset zeroes the LED rows.
    frames = np.tile(ON_HEAD, (2, 1))
    frames[0, [0, 1, 2, 3, *range(8, 16)]] = 0.0
    assert too_much_light(frames).tolist() == [True, False]


def test_a_stream_of_zeros_is_not_light() -> None:
    # An optics stream that never started (all rows 0) is a different fault.
    assert not too_much_light(np.zeros((4, 16))).any()


def test_four_and_eight_channel_presets_only_check_the_ceiling() -> None:
    frames = np.zeros((2, 16))
    frames[:, :4] = 50_000.0  # a 4-channel preset: the other rows stay 0
    frames[1, 2] = OPTICS_FULL_SCALE
    assert too_much_light(frames, sixteen_channels=False).tolist() == [False, True]


# Detector grades for the live view: pulse seen / finding pulse / light leaking / no reading.

RATE = 64.0


def _frames(seconds: float, *, pulse_hz: float | None = 1.2, seed: int = 0) -> np.ndarray:
    """On-head levels, with a heartbeat on every LED row when `pulse_hz` is given."""
    rng = np.random.default_rng(seed)
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    x = np.tile(ON_HEAD, (n, 1))
    for row in range(16):
        if row in (4, 5, 6, 7):  # ambient rows: no heartbeat
            x[:, row] += rng.normal(0, 40, n)
            continue
        beat = 0.004 * ON_HEAD[row] * np.sin(2 * np.pi * pulse_hz * t) if pulse_hz else 0.0
        x[:, row] += beat + rng.normal(0, 0.0004 * ON_HEAD[row] + 1, n)
    return x


def test_a_heartbeat_on_every_detector_is_pulse_seen() -> None:
    grades = detector_grades(_frames(10.0))
    assert grades == {"LO": "pulse", "LI": "pulse", "RI": "pulse", "RO": "pulse"}


def test_noise_without_a_heartbeat_is_still_finding_the_pulse() -> None:
    assert set(detector_grades(_frames(10.0, pulse_hz=None)).values()) == {"finding"}


def test_less_than_eight_seconds_is_still_finding_the_pulse() -> None:
    assert set(detector_grades(_frames(6.0)).values()) == {"finding"}


def test_an_ambient_row_at_the_ceiling_is_light_leaking_on_that_detector_only() -> None:
    x = _frames(10.0)
    x[-10:, 7] = OPTICS_FULL_SCALE  # OPT8: ambient, RO
    grades = detector_grades(x)
    assert grades["RO"] == "light"
    assert grades["LO"] == grades["LI"] == grades["RI"] == "pulse"


def test_leds_zeroed_by_the_headset_are_light_leaking() -> None:
    x = _frames(10.0)
    x[-10:, [0, 8, 12]] = 0.0  # every LED row of LI
    assert detector_grades(x)["LI"] == "light"


def test_rows_that_never_change_are_no_reading() -> None:
    x = _frames(10.0)
    x[:, [2, 10, 14]] = 0.0  # every LED row of LO, ambient still normal
    x[:, 6] = 0.0
    assert detector_grades(x)["LO"] == "none"


def test_presets_without_the_sixteen_channel_layout_have_no_detector_map() -> None:
    assert detector_grades(_frames(10.0), sixteen_channels=False) == {}


def test_no_frames_is_finding() -> None:
    assert set(detector_grades(np.empty((0, 17))).values()) == {"finding"}
