"""Weekly patterns (008 gate): every one has n, an effect and the label "hypothesis"."""

from __future__ import annotations

from pathlib import Path

import pytest

from mufuse.companion.store import DEFAULT_ANSWERS, Source, Store
from mufuse.journal.patterns import MIN_N, Pattern, find, pattern_lines

T0 = 1_800_000_000.0
MIN = 60.0


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "db")


def _checkin(store: Store, session: int, t: float, answer: str, source: Source = "random") -> None:
    c = store.ask(session, t=t, source=source, order=DEFAULT_ANSWERS)
    store.answer(c, t=t + 5, answer=answer)


def _week(store: Store) -> int:
    session = store.start_session(t=T0)
    # 20 random check-ins: daydreaming 4 times overall, 3 of them right after "blink rate higher".
    for i in range(20):
        t = T0 + i * 30 * MIN
        if i in (2, 6, 10):
            store.observation_started(
                session, series="blinks_per_min", direction="higher", t=t - 4 * MIN
            )
            _checkin(store, session, t, "daydreaming")
        elif i == 15:
            _checkin(store, session, t, "daydreaming")
        else:
            _checkin(store, session, t, "on task")
    # Self and shift check-ins right after the same observation never count.
    _checkin(store, session, T0 + 2 * 30 * MIN + 60, "worry", source="self")
    return session


def test_an_observation_followed_by_an_answer_is_a_pattern_with_n_and_effect(store: Store) -> None:
    _week(store)
    patterns = find(store, since=T0 - 1)
    top = patterns[0]
    assert (top.hits, top.n) == (3, 3)
    assert top.answer == "daydreaming"
    assert top.base == pytest.approx(4 / 20)
    assert top.effect_pts == pytest.approx(100 * (1.0 - 0.2))
    assert top.label == "hypothesis"
    assert "blink rate higher" in top.when


def test_context_windows_make_patterns_too(store: Store) -> None:
    session = store.start_session(t=T0)
    for i in range(12):
        t = T0 + i * 30 * MIN
        in_meeting = i < 4
        if in_meeting:
            store.add_context(start=t - MIN, end=t + MIN, tag="meeting", label="Sync", source="ics")
        _checkin(store, session, t, "worry" if in_meeting else "on task")
    (p, *_) = [p for p in find(store, since=T0 - 1) if p.when == "in meetings"]
    assert (p.answer, p.hits, p.n) == ("worry", 4, 4)


def test_fewer_than_three_is_never_shown(store: Store) -> None:
    session = store.start_session(t=T0)
    store.observation_started(session, series="hr_bpm", direction="lower", t=T0)
    _checkin(store, session, T0 + MIN, "memory")
    _checkin(store, session, T0 + 2 * MIN, "memory")
    assert all(p.n >= MIN_N for p in find(store, since=T0 - 1))
    assert find(store, since=T0 - 1) == []


def test_every_line_shown_carries_n_effect_and_hypothesis(store: Store) -> None:
    _week(store)
    patterns = find(store, since=T0 - 1)
    lines = pattern_lines(patterns)
    assert "some will be chance" in lines[0]
    for line in lines[1:]:
        assert "n=" in line
        assert " points" in line
        assert "hypothesis" in line


def test_no_patterns_says_so() -> None:
    assert pattern_lines([])[-1] == "No pattern has enough random check-ins yet (at least 3)."


def test_pattern_is_frozen_with_its_label() -> None:
    p = Pattern(when="x", answer="y", hits=3, n=4, base=0.25)
    assert p.share == 0.75
    assert p.effect_pts == pytest.approx(50.0)
    assert p.label == "hypothesis"
