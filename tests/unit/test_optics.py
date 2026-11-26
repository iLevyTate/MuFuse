from __future__ import annotations

import numpy as np

from mufuse.acquisition.optics import OPTICS_FULL_SCALE, too_much_light

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
