"""The check-in store: every answer kept with where its question came from (005 decisions 1, 5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mufuse.companion.store import DEFAULT_ANSWERS, Source, Store


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "mufuse.db")


def test_a_check_in_is_kept_with_its_source_and_its_answer(store: Store) -> None:
    session = store.start_session(t=100.0, recording="rec-1")
    asked = store.ask(session, t=110.0, source="random", order=("on task", "worry"))
    store.answer(asked, t=113.5, answer="worry")
    (row,) = store.checkins(session)
    assert (row.source, row.answer, row.answered_t) == ("random", "worry", 113.5)
    assert row.order == ("on task", "worry")


def test_own_words_are_kept_as_written(store: Store) -> None:
    session = store.start_session(t=0.0)
    asked = store.ask(session, t=1.0, source="self", order=DEFAULT_ANSWERS)
    store.answer(asked, t=2.0, answer="own words", text="the meeting at three")
    (row,) = store.checkins(session)
    assert row.text == "the meeting at three"


def test_an_expired_check_in_stays_unanswered(store: Store) -> None:
    session = store.start_session(t=0.0)
    asked = store.ask(session, t=1.0, source="random", order=DEFAULT_ANSWERS)
    store.expire(asked, t=121.0)
    (row,) = store.checkins(session)
    assert row.answer is None
    assert row.closed_t == 121.0


def test_answers_are_counted_by_source_never_mixed(store: Store) -> None:
    session = store.start_session(t=0.0)
    sources: list[Source] = ["random", "random", "shift", "self"]
    for i, source in enumerate(sources):
        asked = store.ask(session, t=float(i), source=source, order=DEFAULT_ANSWERS)
        if i != 1:
            store.answer(asked, t=i + 0.5, answer="on task")
    counts = store.compliance()
    assert counts["random"] == (1, 2)  # answered, asked
    assert counts["shift"] == (1, 1)
    assert counts["self"] == (1, 1)


def test_an_answer_cannot_land_twice(store: Store) -> None:
    session = store.start_session(t=0.0)
    asked = store.ask(session, t=1.0, source="random", order=DEFAULT_ANSWERS)
    store.answer(asked, t=2.0, answer="worry")
    with pytest.raises(ValueError, match="closed"):
        store.answer(asked, t=3.0, answer="on task")


def test_the_answer_list_is_the_wearers_to_edit(tmp_path: Path) -> None:
    path = tmp_path / "mufuse.db"
    assert Store(path).answers() == DEFAULT_ANSWERS
    Store(path).set_answers(("on task", "music", "own words"))
    assert Store(path).answers() == ("on task", "music", "own words")  # kept across runs


def test_marks_are_kept_per_session(store: Store) -> None:
    session = store.start_session(t=0.0)
    store.mark(session, t=5.0, label="moment", source="strip")
    assert [(m.t, m.label, m.source) for m in store.marks(session)] == [(5.0, "moment", "strip")]


def test_an_unknown_source_is_refused(store: Store) -> None:
    session = store.start_session(t=0.0)
    with pytest.raises(ValueError, match="source"):
        store.ask(session, t=1.0, source="guess", order=DEFAULT_ANSWERS)  # type: ignore[arg-type]
