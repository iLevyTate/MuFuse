"""Eye marks and blinks on the forehead sensors (contracts/quality-rules.md, section 4)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

import numpy as np
import pytest
from scipy import signal

from mufuse.acquisition.types import FloatArray, StreamKind
from mufuse.quality.answer import Blink
from mufuse.quality.blink import Envelope, EyeDetector, eye_events, limit
from mufuse.quality.rules import RULES, Rules
from mufuse.quality.stretch import Stretch, StretchCutter
from tests.conftest import QUICK, FakeClock, eeg_chunk, motion_chunk, rehearse

FS = 256
T0 = 100.0
RNG = np.random.default_rng(21)


def _rest(n: int) -> FloatArray:
    """Two forehead sensors at rest, like the simulator: alpha, noise, an offset."""
    t = np.arange(n) / FS
    return -54.0 + 20.0 * np.sin(2 * np.pi * 10 * t)[:, None] + 8.0 * RNG.standard_normal((n, 2))


def _bump(x: FloatArray, at_s: float, *, peak: float = 150.0, column: int | None = None) -> None:
    """A blink: a 0.3 s half sine on one forehead sensor, or on both."""
    first, n = round(at_s * FS), round(0.3 * FS)
    shape = peak * np.sin(np.pi * np.arange(n) / n)
    columns = [0, 1] if column is None else [column]
    for c in columns:
        x[first : first + n, c] += shape


def _stretches(forehead: FloatArray) -> list[Stretch]:
    seconds = forehead.shape[0] // FS
    eeg = np.column_stack([np.zeros(len(forehead)), forehead, np.zeros(len(forehead))])
    cutter = StretchCutter()
    chunks = [eeg_chunk(eeg, T0), motion_chunk(np.zeros((seconds * 52, 6)), T0)]
    items = cutter.add(chunks) + cutter.finish()
    return [s for s in items if isinstance(s, Stretch)]


def _detect(
    forehead: FloatArray, in_use: tuple[bool, bool] = (True, True), rules: Rules = RULES
) -> tuple[list[str], list[Blink]]:
    detector, marks, found = EyeDetector(rules), [], []
    for stretch in _stretches(forehead):
        mark, blinks = detector.judge(stretch, in_use)
        marks.append(mark)
        found += blinks
    found += detector.close()
    return marks, found


def _onsets(found: Sequence[Blink]) -> list[float]:
    return [round(b.t - T0, 3) for b in found]


# The envelope ------------------------------------------------------------------------------


def test_the_envelope_is_the_same_in_one_piece_and_in_pieces() -> None:
    x = _rest(3000)
    whole = Envelope(2).step(x)
    pieces = Envelope(2)
    parts = [pieces.step(x[:7]), pieces.step(x[7:1000]), pieces.step(x[1000:])]
    np.testing.assert_array_equal(np.vstack(parts), whole)


def test_a_look_ahead_does_not_move_the_envelope_on() -> None:
    x = _rest(1000)
    envelope = Envelope(2)
    envelope.step(x[:500])
    peek = envelope.step(x[500:600], keep=False)
    np.testing.assert_array_equal(envelope.step(x[500:600]), peek)


def test_the_envelope_starts_from_zero_at_the_anchor() -> None:
    x = _rest(64)
    sos = signal.butter(2, [1, 10], btype="bandpass", fs=FS, output="sos")
    filtered = signal.sosfilt(sos, x[:, 0])
    assert Envelope(1).step(x[:, :1])[0, 0] == pytest.approx(abs(filtered[0]) / 32)
    assert Envelope(1).step(x[:, :1])[31, 0] == pytest.approx(np.abs(filtered[:32]).mean())


# The limit and eye events ------------------------------------------------------------------


def test_the_limit_is_median_plus_four_robust_spreads_and_at_least_15_uv() -> None:
    assert limit(np.array([38.0, 40.0, 42.0])) == pytest.approx(40.0 + 4 * 1.4826 * 2.0)
    assert limit(np.full(50, 5.0)) == RULES.eye_floor_uv == 15.0
    assert limit(np.empty(0)) == 15.0


def test_an_eye_event_is_a_run_of_16_samples_or_more() -> None:
    above = np.array([False] * 3 + [True] * 15 + [False] + [True] * 16 + [False])
    assert eye_events(above) == [(19, 34)]
    assert eye_events(np.ones(20, dtype=bool)) == [(0, 19)]
    assert eye_events(np.zeros(20, dtype=bool)) == []


def test_the_limit_comes_from_the_30_s_before_the_stretch() -> None:
    x = _rest(70 * FS)
    t = np.arange(20 * FS) / FS
    x[: 20 * FS] += 120.0 * np.sin(2 * np.pi * 5 * t)[:, None]  # loud for the first 20 s
    _bump(x, 25.3, peak=100.0)  # the loud stretch still sets the limit
    _bump(x, 55.3, peak=100.0)  # 30 s later it no longer does
    _, found = _detect(x)
    assert len(found) == 1
    assert 55.3 <= found[0].t - T0 <= 55.45


# Both sensors, the mark window, the warm-up ------------------------------------------------


def test_every_forehead_sensor_in_use_must_be_above() -> None:
    x = _rest(20 * FS)
    _bump(x, 10.3, column=0)  # only AF7 sees it
    assert _detect(x)[1] == []
    assert _onsets(_detect(x, (True, False))[1]) == [pytest.approx(10.33, abs=0.05)]


def test_the_eye_mark_covers_32_samples_either_side_of_the_stretch() -> None:
    x = _rest(40 * FS)
    for at in (10.3, 20.9, 30.02):
        _bump(x, at)
    marks, _ = _detect(x)
    # 30.02: the event starts 21 samples into stretch 30, inside the 32 that stretch 29 looks
    # ahead. Each event (about 0.54 s) and the band-pass swinging back after it (about 0.7-0.9 s
    # after the onset) reach the 32 samples before the stretch that follows.
    yes = [i for i, mark in enumerate(marks) if mark == "yes"]
    assert yes == [10, 11, 20, 21, 29, 30, 31]
    assert marks[9] == marks[19] == marks[28] == marks[32] == "no"


def test_no_mark_and_no_blink_before_the_sixth_stretch_or_without_a_forehead_sensor() -> None:
    x = _rest(12 * FS)
    _bump(x, 2.3)
    _bump(x, 8.3)
    marks, found = _detect(x)
    assert marks[:5] == ["unavailable"] * 5
    assert marks[8] == "yes"
    assert _onsets(found) == [pytest.approx(8.33, abs=0.05)]
    marks, found = _detect(x, (False, False))
    assert set(marks) == {"unavailable"}
    assert found == []


def test_a_run_longer_than_307_samples_marks_but_is_no_blink() -> None:
    x = _rest(20 * FS)
    t = np.arange(round(1.5 * FS)) / FS
    x[10 * FS : 10 * FS + len(t)] += 100.0 * np.sin(2 * np.pi * 4 * t)[:, None]  # eyes closed
    marks, found = _detect(x)
    assert marks[10] == marks[11] == "yes"
    assert found == []


def test_a_blink_less_than_0_8_s_after_the_previous_reported_one_is_dropped() -> None:
    x = _rest(30 * FS)
    for at in (10.3, 20.3, 21.4):
        _bump(x, at)  # a large blink: the band-pass swings back over the limit 0.7 s later
    every = _onsets(_detect(x, rules=replace(RULES, blink_apart_s=0.0))[1])
    kept: list[float] = []
    for t in every:
        if not kept or t - kept[-1] >= RULES.blink_apart_s:
            kept.append(t)
    assert _onsets(_detect(x)[1]) == kept
    assert len(every) > len(kept)  # the swing-backs were there, and the rule dropped them
    assert [round(t) for t in kept] == [10, 20, 21]


def test_a_blink_has_its_duration() -> None:
    x = _rest(20 * FS)
    _bump(x, 10.3)
    (blink,) = _detect(x)[1]
    assert 0.2 <= blink.duration_s <= 0.6


def test_simulated_blinks_are_found_at_their_times(clock: FakeClock) -> None:
    reads = rehearse(replace(QUICK, blinks=((10.0, 15.0),)), clock, 20.0)
    eeg = [c for read in reads for c in read if c.kind is StreamKind.EEG]
    first = eeg[0].timestamps[0]
    cutter, detector = StretchCutter(), EyeDetector()
    found: list[Blink] = []
    for read in reads:
        for item in cutter.add(read):
            if isinstance(item, Stretch):
                found += detector.judge(item, (True, True))[1]
    for item in cutter.finish():
        if isinstance(item, Stretch):
            found += detector.judge(item, (True, True))[1]
    found += detector.close()
    onsets = [b.t - first for b in found]
    assert len(onsets) == 5
    for second, onset in zip(range(10, 15), onsets, strict=True):
        assert second <= onset <= second + 0.15
