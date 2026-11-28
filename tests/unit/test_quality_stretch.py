"""Cutting the streams into stretches (contracts/quality-rules.md, section 1)."""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from mufuse.acquisition.types import Chunk, StreamKind
from mufuse.quality.stretch import NoData, Stretch, StretchCutter
from tests.conftest import eeg_chunk, motion_chunk

EEG_HZ, MOTION_HZ = 256, 52


def _eeg(seconds: float, t0: float = 100.0, first: int = 0) -> Chunk:
    """EEG whose TP9 column counts the samples, so a test can see which ones a stretch holds."""
    n = round(seconds * EEG_HZ)
    data = np.zeros((n, 4))
    data[:, 0] = first + np.arange(n)
    return eeg_chunk(data, t0)


def _motion(seconds: float, t0: float = 100.0) -> Chunk:
    return motion_chunk(np.ones((round(seconds * MOTION_HZ), 6)), t0)


def _cut(cutter: StretchCutter, *chunks: Chunk) -> list[Stretch | NoData]:
    return cutter.add(list(chunks))


def _stretch(item: Stretch | NoData) -> Stretch:
    assert isinstance(item, Stretch)
    return item


def test_every_256_samples_from_the_first_one_are_a_stretch() -> None:
    stretches = [_stretch(s) for s in _cut(StretchCutter(), _eeg(3.5), _motion(3.5))]
    assert [s.start for s in stretches] == [100.0, 101.0, 102.0]
    assert [s.end for s in stretches] == [101.0, 102.0, 103.0]
    assert [s.index for s in stretches] == [0, 256, 512]
    for s in stretches:
        assert s.eeg.shape == (256, 4)
        assert s.t.shape == (256,)
        assert s.t[0] == s.start
        assert s.eeg[:, 0].tolist() == list(range(s.index, s.index + 256))
        assert s.ahead[:, 0].tolist() == list(range(s.index + 256, s.index + 320))
        assert s.ahead_t.shape == (64,)
        assert s.ahead_t[0] == pytest.approx(s.end)


def test_the_motion_samples_of_a_stretch_start_at_its_start_and_stop_before_its_end() -> None:
    motion = motion_chunk(np.arange(52 * 3)[:, None] * np.ones((1, 6)), 100.0)
    first, second = (_stretch(s) for s in _cut(StretchCutter(), _eeg(2.5), motion))
    assert first.motion[:, 0].tolist() == list(range(52))  # 100.0 <= t < 101.0
    assert second.motion[:, 0].tolist() == list(range(52, 104))
    assert first.motion.shape == (52, 6)


def test_a_stretch_waits_for_64_more_eeg_samples() -> None:
    cutter = StretchCutter()
    assert _cut(cutter, _eeg(1.0), _motion(2.0)) == []
    assert _cut(cutter, eeg_chunk(np.zeros((63, 4)), 101.0)) == []
    (stretch,) = _cut(cutter, eeg_chunk(np.zeros((1, 4)), 101.0 + 63 / 256))
    assert _stretch(stretch).ahead.shape == (64, 4)


def test_a_stretch_waits_for_motion_up_to_its_end() -> None:
    cutter = StretchCutter()
    motion = _motion(53 / 52)  # the last sample is stamped 101.0
    early = Chunk(motion.kind, motion.timestamps[:47], motion.data[:47])
    rest = Chunk(motion.kind, motion.timestamps[47:], motion.data[47:])
    assert _cut(cutter, _eeg(1.5), early) == []
    (stretch,) = _cut(cutter, rest)
    assert _stretch(stretch).motion.shape[0] == 52


def test_without_motion_a_stretch_is_judged_one_second_after_its_end() -> None:
    cutter = StretchCutter()
    assert _cut(cutter, _eeg(1.99)) == []
    (stretch,) = _cut(cutter, eeg_chunk(np.zeros((4, 4)), 100.0 + 509 / 256))  # reaches 102.0
    assert _stretch(stretch).motion.shape == (0, 6)
    assert _stretch(stretch).ahead.shape == (64, 4)  # never more than 64, whatever has come


def test_motion_that_stops_in_a_stretch_leaves_the_samples_that_came() -> None:
    (stretch,) = _cut(StretchCutter(), _eeg(2.1), _motion(0.5))
    assert _stretch(stretch).motion.shape[0] == 26


def test_a_gap_judges_what_waits_and_gives_one_no_data_answer() -> None:
    before = _eeg(1.1)  # one full stretch and 26 samples that are not judged
    after = _eeg(2.5, t0=105.0, first=5000)
    out = _cut(StretchCutter(), before, _motion(8.0), after)
    assert [type(s) for s in out] == [Stretch, NoData, Stretch, Stretch]
    first, gap, second, third = out
    assert _stretch(first).ahead.shape[0] == 26  # the samples that exist
    assert gap == NoData(101.0, 105.0)
    assert (_stretch(second).start, _stretch(second).index) == (105.0, 0)  # a new anchor
    assert _stretch(second).eeg[0, 0] == 5000
    assert (_stretch(third).start, _stretch(third).index) == (106.0, 256)


def test_a_gap_before_the_first_full_stretch_starts_at_the_anchor() -> None:
    out = _cut(StretchCutter(), _eeg(0.5), _eeg(0.2, t0=103.0))
    assert out == [NoData(100.0, 103.0)]


def test_a_step_of_a_quarter_second_is_not_a_gap() -> None:
    late = eeg_chunk(np.zeros((319, 4)), 100.0 + 255 / 256 + 0.25)
    out = _cut(StretchCutter(), _eeg(1.0), _motion(3.0), late)
    assert [type(s) for s in out] == [Stretch]
    later = eeg_chunk(np.zeros((319, 4)), 100.0 + 255 / 256 + 0.26)
    out = _cut(StretchCutter(), _eeg(1.0), _motion(3.0), later)
    assert [type(s) for s in out] == [Stretch, NoData]
    assert out[1] == NoData(101.0, 100.0 + 255 / 256 + 0.26)


def test_finish_judges_the_stretches_that_wait_and_not_the_rest() -> None:
    cutter = StretchCutter()
    assert _cut(cutter, _eeg(2.0)) == []  # no motion, and the EEG has not reached 102.0
    first, last = (_stretch(s) for s in cutter.finish())
    assert (first.ahead.shape[0], last.ahead.shape[0]) == (64, 0)
    assert cutter.finish() == []


def test_finish_leaves_out_the_samples_after_the_last_full_stretch() -> None:
    cutter = StretchCutter()
    (first,) = _cut(cutter, _eeg(2.1))  # no motion: judged when the EEG reaches 102.0
    (last,) = cutter.finish()
    assert _stretch(first).index == 0
    assert (_stretch(last).index, _stretch(last).ahead.shape[0]) == (256, round(2.1 * 256) - 512)
    assert cutter.finish() == []


def test_other_streams_are_ignored() -> None:
    optics = Chunk(StreamKind.OPTICS, np.array([100.0]), np.zeros((1, 17)))
    assert _cut(StretchCutter(), optics) == []


def test_the_cutter_does_not_keep_the_whole_session() -> None:
    cutter = StretchCutter()
    for second in range(120):
        cutter.add([_eeg(1.0, t0=100.0 + second), _motion(1.0, t0=100.0 + second)])
    assert cutter.held_samples < 3 * (EEG_HZ + MOTION_HZ)


def _session(rng: np.random.Generator) -> tuple[Chunk, ...]:
    """Twelve seconds of both streams with a dropout from second 5 to second 7.3."""
    eeg_a = eeg_chunk(rng.standard_normal((5 * 256 + 100, 4)), 50.0)
    eeg_b = eeg_chunk(rng.standard_normal((5 * 256 - 31, 4)), 57.3)
    motion_a = motion_chunk(rng.standard_normal((5 * 52 + 20, 6)), 50.0)
    motion_b = motion_chunk(rng.standard_normal((3 * 52, 6)), 57.3)  # motion ends early
    return eeg_a, eeg_b, motion_a, motion_b


def _deliver(streams: tuple[Chunk, ...], rng: np.random.Generator) -> list[list[Chunk]]:
    """The same samples as a source delivers them: every stream up to one time, then the next."""
    end = max(float(c.timestamps[-1]) for c in streams) + 1.0
    edges = [min(float(c.timestamps[0]) for c in streams)]
    while edges[-1] < end:
        edges.append(edges[-1] + float(rng.uniform(0.01, 0.9)))
    reads: list[list[Chunk]] = []
    for lo, hi in itertools.pairwise(edges):
        read: list[Chunk] = []
        for c in streams:
            rows = (c.timestamps >= lo) & (c.timestamps < hi)
            if rows.any():
                read.append(Chunk(c.kind, c.timestamps[rows], c.data[rows]))
        reads.append([read[i] for i in rng.permutation(len(read))])
    return reads


def _same(a: Stretch | NoData, b: Stretch | NoData) -> bool:
    if isinstance(a, NoData) or isinstance(b, NoData):
        return a == b
    return (
        (a.start, a.end, a.index) == (b.start, b.end, b.index)
        and np.array_equal(a.t, b.t)
        and np.array_equal(a.eeg, b.eeg)
        and np.array_equal(a.ahead, b.ahead)
        and np.array_equal(a.ahead_t, b.ahead_t)
        and np.array_equal(a.motion, b.motion)
    )


@pytest.mark.parametrize("seed", range(8))
def test_the_stretches_do_not_depend_on_how_the_samples_are_delivered(seed: int) -> None:
    streams = _session(np.random.default_rng(99))
    whole = StretchCutter()
    expected = whole.add(list(streams)) + whole.finish()
    assert [type(s) for s in expected].count(NoData) == 1
    assert len(expected) == 10  # 5 stretches, the gap, 4 stretches

    cutter = StretchCutter()
    got: list[Stretch | NoData] = []
    for read in _deliver(streams, np.random.default_rng(seed)):
        got += cutter.add(read)
    got += cutter.finish()
    assert len(got) == len(expected)
    assert all(_same(a, b) for a, b in zip(got, expected, strict=True))
