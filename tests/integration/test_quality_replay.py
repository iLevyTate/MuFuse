"""The same answers live and replayed (SC-005, contracts/quality-interface.md)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from mufuse.acquisition.playback import PlaybackSource
from mufuse.acquisition.simulated import Rehearsal, Wearer
from mufuse.acquisition.types import Chunk, StreamKind
from mufuse.cli import (
    SourceKind,
    _Attempt,  # pyright: ignore[reportPrivateUsage]
    _run,  # pyright: ignore[reportPrivateUsage]
)
from mufuse.live_view import LiveStats
from mufuse.quality.answer import SessionQuality
from mufuse.quality.engine import QualityEngine, judge
from mufuse.recording.reader import LoadedSession, load_session
from mufuse.recording.writer import SessionWriter
from tests.conftest import QUICK, FakeClock

TICK_S = 0.25
EVERYTHING = replace(
    QUICK,
    blinks=((8.0, 12.0),),
    clench=((13.0, 15.0),),
    turns=((16.0, 18.0),),
    lifted=((19.0, 22.0, "AF8"),),
    noisy=((23.0, 25.0, "TP10"),),
)


def _record(tmp_path: Path, clock: FakeClock, wearer: Wearer, seconds: float) -> LiveStats:
    """Record like `mufuse record`, keeping what the live view judged."""
    stats = LiveStats(clock)
    rehearsal = Rehearsal(wearer, clock=clock, sleep=clock.advance)
    _run(
        _Attempt("record", SourceKind.sim, "p1041", clock.now),
        rehearsal.source,
        seconds,
        lambda src: SessionWriter.create(tmp_path, src.device, src.streams, clock=clock),
        clock=clock,
        sleep=lambda _: clock.advance(TICK_S),
        read_key=rehearsal.read_key,
        stats=stats,
    )
    return stats


def _session(tmp_path: Path) -> LoadedSession:
    (folder,) = [p for p in tmp_path.iterdir() if p.is_dir()]
    return load_session(folder)


def _assert_same(live: LiveStats, replayed: SessionQuality) -> None:
    assert live.answers == replayed.answers
    assert live.blinks == replayed.blinks


def _played(path: Path, seed: int) -> SessionQuality:
    """The answers of `PlaybackSource`, read at random moments: chunks of random size."""
    clock, rng = FakeClock(), np.random.default_rng(seed)
    source = PlaybackSource(path, clock=clock)
    source.start()
    engine, answers, blinks = QualityEngine(), [], []
    while not source.exhausted:
        clock.advance(float(rng.uniform(0.004, 0.9)))
        judged = engine.feed(source.read())
        answers += judged.answers
        blinks += judged.blinks
    judged = engine.finish()
    return SessionQuality.of((*answers, *judged.answers), (*blinks, *judged.blinks))


def test_live_answers_equal_the_recording_judged_and_played_back(
    tmp_path: Path, clock: FakeClock
) -> None:
    live = _record(tmp_path, clock, EVERYTHING, 30.0)
    session = _session(tmp_path)
    assert len(live.answers) >= 28
    assert len(live.blinks) == 4
    _assert_same(live, judge(session))
    for seed in (1, 2, 3):
        _assert_same(live, _played(session.path, seed))


def test_live_and_replay_agree_across_a_dropout(tmp_path: Path, clock: FakeClock) -> None:
    live = _record(tmp_path, clock, replace(EVERYTHING, off=((12.0, 15.0),)), 30.0)
    session = _session(tmp_path)
    assert session.gaps
    assert any(a.no_data for a in live.answers)
    _assert_same(live, judge(session))
    _assert_same(live, _played(session.path, 4))


def test_live_and_replay_agree_when_the_motion_stream_stops(
    tmp_path: Path, clock: FakeClock
) -> None:
    _record(tmp_path, clock, EVERYTHING, 30.0)
    session = _session(tmp_path)
    ts, data = session.streams[StreamKind.MOTION]
    keep = ts < ts[0] + 15.0
    cut = replace(session, streams={**session.streams, StreamKind.MOTION: (ts[keep], data[keep])})
    replayed = judge(cut)
    assert {a.movement for a in replayed.answers[17:]} == {"unknown"}
    rng = np.random.default_rng(5)
    engine, answers = QualityEngine(), []
    streams = [(k, *cut.streams[k]) for k in (StreamKind.EEG, StreamKind.MOTION)]
    t, last = float(streams[0][1][0]), float(streams[0][1][-1])
    while t <= last:
        step = float(rng.uniform(0.01, 0.7))
        chunks = []
        for kind, kts, kdata in streams:
            rows = (kts >= t) & (kts < t + step)
            if rows.any():
                chunks.append(Chunk(kind, kts[rows], kdata[rows]))
        answers += engine.feed(chunks).answers
        t += step
    answers += engine.finish().answers
    assert tuple(answers) == replayed.answers
