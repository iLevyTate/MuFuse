"""One session as a timeline: check-ins (every source, said which), observations, marks, notes
and context windows, in time order (008)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from mufuse.companion.store import Store
from mufuse.observe.observations import NAMES


@dataclass(frozen=True)
class Event:
    t: float
    kind: str  # session | checkin | observation | mark | note | context
    text: str


def timeline(store: Store, session: int) -> list[Event]:
    sessions = {s: (start, end) for s, start, end in store.sessions()}
    if session not in sessions:
        raise KeyError(f"no session {session}")
    start, end = sessions[session]
    stop = end if end is not None else float("inf")
    events = [Event(start, "session", "session started")]
    for c in store.checkins(session):
        said = f"answered '{c.answer}'" if c.answer else "not answered"
        events.append(Event(c.asked_t, "checkin", f"check-in ({c.source}): {said}"))
    for o in store.observations(session=session):
        name = NAMES.get(o.series, o.series)
        length = "" if o.end is None else f" for {round((o.end - o.start) / 60)} min"
        events.append(Event(o.start, "observation", f"{name} {o.direction} than usual{length}"))
    for m in store.marks(session):
        events.append(Event(m.t, "mark", f"mark: {m.label}"))
    for n in store.notes(since=start, until=stop):
        tags = f" [{', '.join(n.tags)}]" if n.tags else ""
        events.append(Event(n.t, "note", f"note: {n.text}{tags}"))
    for w in store.context(since=start, until=stop):
        events.append(Event(w.start, "context", f"{w.tag}: {w.label} until {_hm(w.end)}"))
    if end is not None:
        events.append(Event(end, "session", "session ended"))
    return sorted(events, key=lambda e: (e.t, e.kind))


def _hm(t: float) -> str:
    return datetime.fromtimestamp(t).strftime("%H:%M")


def timeline_lines(events: list[Event]) -> list[str]:
    return [f"{_hm(e.t)}  {e.text}" for e in events]
