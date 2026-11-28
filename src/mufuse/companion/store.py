"""The check-in store: sessions, check-ins with their source, marks, and the wearer's answer list.

One SQLite file in the user's own data folder (constitution I). A check-in's source never changes
and hit rates are never counted across sources (005 decision 1).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args

from platformdirs import user_data_path

Source = Literal["random", "shift", "self"]
SOURCES: tuple[Source, ...] = get_args(Source)

DEFAULT_ANSWERS = (
    "on task",
    "planning",
    "daydreaming",
    "worry",
    "stuck on a thought",
    "memory",
    "urge",
    "feeling low",
    "nothing much",
    "own words",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY, started_t REAL NOT NULL, ended_t REAL, recording TEXT
);
CREATE TABLE IF NOT EXISTS checkins (
    id INTEGER PRIMARY KEY,
    session INTEGER NOT NULL REFERENCES sessions(id),
    asked_t REAL NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('random', 'shift', 'self')),
    shown_order TEXT NOT NULL,
    answer TEXT,
    text TEXT,
    answered_t REAL,
    closed_t REAL
);
CREATE TABLE IF NOT EXISTS marks (
    id INTEGER PRIMARY KEY,
    session INTEGER NOT NULL REFERENCES sessions(id),
    t REAL NOT NULL, label TEXT NOT NULL, source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS scores (
    checkin INTEGER NOT NULL REFERENCES checkins(id),
    interpreter TEXT NOT NULL,
    version INTEGER NOT NULL,
    score REAL,
    fired INTEGER NOT NULL,
    after_insight INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (checkin, interpreter)
);
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY,
    session INTEGER NOT NULL REFERENCES sessions(id),
    series TEXT NOT NULL, direction TEXT NOT NULL, start_t REAL NOT NULL, end_t REAL
);
CREATE TABLE IF NOT EXISTS journal (
    id INTEGER PRIMARY KEY, session INTEGER, t REAL NOT NULL, text TEXT NOT NULL,
    tags TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS context (
    id INTEGER PRIMARY KEY, start_t REAL NOT NULL, end_t REAL NOT NULL, tag TEXT NOT NULL,
    label TEXT NOT NULL, source TEXT NOT NULL,
    UNIQUE (start_t, end_t, tag, label, source)
);
CREATE TABLE IF NOT EXISTS interpreters (
    id TEXT PRIMARY KEY,
    state TEXT NOT NULL DEFAULT 'shadow',
    last_look INTEGER NOT NULL DEFAULT 0,
    early INTEGER NOT NULL DEFAULT 0
);
"""


def default_path() -> Path:
    return user_data_path("mufuse", appauthor=False) / "mufuse.db"


@dataclass(frozen=True)
class CheckIn:
    id: int
    session: int
    asked_t: float
    source: Source
    order: tuple[str, ...]
    answer: str | None
    text: str | None
    answered_t: float | None
    closed_t: float | None


@dataclass(frozen=True)
class Mark:
    t: float
    label: str
    source: str


class Store:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # The server answers requests on several threads; every write is one short statement.
        self._db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._db.executescript(_SCHEMA)

    def close(self) -> None:
        self._db.close()

    # Sessions and marks ------------------------------------------------------------------------

    def start_session(self, *, t: float, recording: str | None = None) -> int:
        cur = self._db.execute(
            "INSERT INTO sessions (started_t, recording) VALUES (?, ?)", (t, recording)
        )
        return int(cur.lastrowid or 0)

    def end_session(self, session: int, *, t: float) -> None:
        self._db.execute("UPDATE sessions SET ended_t = ? WHERE id = ?", (t, session))

    def mark(self, session: int, *, t: float, label: str, source: str) -> None:
        self._db.execute(
            "INSERT INTO marks (session, t, label, source) VALUES (?, ?, ?, ?)",
            (session, t, label, source),
        )

    def marks(self, session: int) -> list[Mark]:
        rows = self._db.execute(
            "SELECT t, label, source FROM marks WHERE session = ? ORDER BY t", (session,)
        )
        return [Mark(float(t), str(label), str(source)) for t, label, source in rows]

    # Check-ins ---------------------------------------------------------------------------------

    def ask(self, session: int, *, t: float, source: Source, order: Sequence[str]) -> int:
        if source not in SOURCES:
            raise ValueError(f"unknown source {source!r}: one of {', '.join(SOURCES)}")
        cur = self._db.execute(
            "INSERT INTO checkins (session, asked_t, source, shown_order) VALUES (?, ?, ?, ?)",
            (session, t, source, json.dumps(list(order))),
        )
        return int(cur.lastrowid or 0)

    def answer(self, checkin: int, *, t: float, answer: str, text: str | None = None) -> None:
        cur = self._db.execute(
            "UPDATE checkins SET answer = ?, text = ?, answered_t = ?, closed_t = ?"
            " WHERE id = ? AND closed_t IS NULL",
            (answer, text, t, t, checkin),
        )
        if cur.rowcount == 0:
            raise ValueError(f"check-in {checkin} is closed or unknown")

    def expire(self, checkin: int, *, t: float) -> None:
        self._db.execute(
            "UPDATE checkins SET closed_t = ? WHERE id = ? AND closed_t IS NULL", (t, checkin)
        )

    def checkins(self, session: int | None = None) -> list[CheckIn]:
        query = (
            "SELECT id, session, asked_t, source, shown_order, answer, text, answered_t, closed_t"
            " FROM checkins"
        )
        args: tuple[int, ...] = ()
        if session is not None:
            query, args = query + " WHERE session = ?", (session,)
        out: list[CheckIn] = []
        for row in self._db.execute(query + " ORDER BY asked_t", args):
            id_, sess, asked, source, order, answer, text, answered, closed = row
            out.append(
                CheckIn(
                    int(id_),
                    int(sess),
                    float(asked),
                    source,
                    tuple(json.loads(order)),
                    answer,
                    text,
                    answered,
                    closed,
                )
            )
        return out

    def compliance(self) -> dict[Source, tuple[int, int]]:
        """Per source: (answered, asked), over every session."""
        counts: dict[Source, tuple[int, int]] = dict.fromkeys(SOURCES, (0, 0))
        rows = self._db.execute(
            "SELECT source, COUNT(answer), COUNT(*) FROM checkins GROUP BY source"
        )
        for source, answered, asked in rows:
            counts[source] = (int(answered), int(asked))
        return counts

    # The answer list ---------------------------------------------------------------------------

    def answers(self) -> tuple[str, ...]:
        row = self._db.execute("SELECT value FROM settings WHERE key = 'answers'").fetchone()
        return DEFAULT_ANSWERS if row is None else tuple(json.loads(row[0]))

    def setting(self, key: str) -> str | None:
        row = self._db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row[0])

    def set_setting(self, key: str, value: str) -> None:
        self._db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def set_answers(self, answers: Sequence[str]) -> None:
        self._db.execute(
            "INSERT INTO settings (key, value) VALUES ('answers', ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (json.dumps(list(answers)),),
        )

    # Interpreters (006) ------------------------------------------------------------------------

    def add_score(
        self,
        checkin: int,
        *,
        interpreter: str,
        version: int,
        score: float | None,
        fired: bool,
        after_insight: bool = False,
    ) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO scores VALUES (?, ?, ?, ?, ?, ?)",
            (checkin, interpreter, version, score, int(fired), int(after_insight)),
        )

    def scored(self, interpreter: str) -> list[Scored]:
        """Answered random check-ins with a score, in time order: what an evaluation reads.

        Check-ins of another source, without a score, or asked soon after an insight was shown
        are left out (constitution V; 006 decisions 6 and 9).
        """
        rows = self._db.execute(
            "SELECT c.asked_t, s.score, c.answer FROM scores s JOIN checkins c ON c.id = s.checkin"
            " WHERE s.interpreter = ? AND c.source = 'random' AND c.answer IS NOT NULL"
            " AND s.score IS NOT NULL AND s.after_insight = 0 ORDER BY c.asked_t",
            (interpreter,),
        )
        return [Scored(float(t), float(score), str(answer)) for t, score, answer in rows]

    def interpreter(self, id_: str) -> InterpreterState:
        row = self._db.execute(
            "SELECT state, last_look, early FROM interpreters WHERE id = ?", (id_,)
        ).fetchone()
        if row is None:
            return InterpreterState(id_, "shadow", 0, False)
        return InterpreterState(id_, row[0], int(row[1]), bool(row[2]))

    def set_interpreter(self, state: InterpreterState) -> None:
        self._db.execute(
            "INSERT INTO interpreters (id, state, last_look, early) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET state = excluded.state,"
            " last_look = excluded.last_look, early = excluded.early",
            (state.id, state.state, state.last_look, int(state.early)),
        )

    # Journal, observations, context (008) -----------------------------------------------------

    def observation_started(self, session: int, *, series: str, direction: str, t: float) -> int:
        cur = self._db.execute(
            "INSERT INTO observations (session, series, direction, start_t) VALUES (?, ?, ?, ?)",
            (session, series, direction, t),
        )
        return int(cur.lastrowid or 0)

    def observation_ended(self, session: int, *, series: str, t: float) -> None:
        self._db.execute(
            "UPDATE observations SET end_t = ? WHERE session = ? AND series = ? AND end_t IS NULL",
            (t, session, series),
        )

    def observations(self, *, since: float = 0.0, session: int | None = None) -> list[Observed]:
        query = (
            "SELECT session, series, direction, start_t, end_t FROM observations WHERE start_t >= ?"
        )
        args: tuple[float | int, ...] = (since,)
        if session is not None:
            query, args = query + " AND session = ?", (since, session)
        rows = self._db.execute(query + " ORDER BY start_t", args)
        return [Observed(int(a), str(b), str(c), float(d), e) for a, b, c, d, e in rows]

    def note(
        self, *, t: float, text: str, tags: Sequence[str] = (), session: int | None = None
    ) -> int:
        cur = self._db.execute(
            "INSERT INTO journal (session, t, text, tags) VALUES (?, ?, ?, ?)",
            (session, t, text, json.dumps(list(tags))),
        )
        return int(cur.lastrowid or 0)

    def notes(self, *, since: float = 0.0, until: float = float("inf")) -> list[Note]:
        rows = self._db.execute(
            "SELECT session, t, text, tags FROM journal WHERE t >= ? AND t <= ? ORDER BY t",
            (since, until if until != float("inf") else 1e18),
        )
        return [Note(s, float(t), str(x), tuple(json.loads(g))) for s, t, x, g in rows]

    def add_context(self, *, start: float, end: float, tag: str, label: str, source: str) -> bool:
        """A time window with a tag; False when the same window was imported before."""
        cur = self._db.execute(
            "INSERT OR IGNORE INTO context (start_t, end_t, tag, label, source)"
            " VALUES (?, ?, ?, ?, ?)",
            (start, end, tag, label, source),
        )
        return cur.rowcount > 0

    def context(self, *, since: float = 0.0, until: float = 1e18) -> list[Context]:
        rows = self._db.execute(
            "SELECT start_t, end_t, tag, label FROM context WHERE end_t >= ? AND start_t <= ?"
            " ORDER BY start_t",
            (since, until),
        )
        return [Context(float(a), float(b), str(c), str(d)) for a, b, c, d in rows]

    def sessions(self, *, since: float = 0.0) -> list[tuple[int, float, float | None]]:
        rows = self._db.execute(
            "SELECT id, started_t, ended_t FROM sessions WHERE started_t >= ? ORDER BY started_t",
            (since,),
        )
        return [(int(i), float(a), b) for i, a, b in rows]


@dataclass(frozen=True)
class Observed:
    session: int
    series: str
    direction: str
    start: float
    end: float | None


@dataclass(frozen=True)
class Note:
    session: int | None
    t: float
    text: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class Context:
    start: float
    end: float
    tag: str
    label: str


@dataclass(frozen=True)
class Scored:
    asked_t: float
    score: float
    answer: str


@dataclass(frozen=True)
class InterpreterState:
    id: str
    state: str  # "shadow" | "promoted"
    last_look: int
    early: bool  # early feedback switched on for it
