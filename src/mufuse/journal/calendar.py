"""Meetings from a calendar file the wearer exports (.ics), read with the standard library only
(008 decision 4). No account and no network: the file is read once and its events are stored as
`meeting` windows. All-day events are skipped; recurring events count once (no RRULE expansion).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from mufuse.companion.store import Store


@dataclass(frozen=True)
class Event:
    start: float
    end: float
    title: str


def _unfold(text: str) -> list[str]:
    """iCalendar folds long lines: a line starting with a space or tab continues the one before."""
    lines: list[str] = []
    for raw in text.splitlines():
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _when(name_params: str, value: str) -> float | None:
    """An iCalendar date-time as epoch seconds; None for all-day dates."""
    if "VALUE=DATE" in name_params.upper() and "DATE-TIME" not in name_params.upper():
        return None
    value = value.strip()
    if len(value) == 8:  # a bare date: all day
        return None
    try:
        if value.endswith("Z"):
            return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC).timestamp()
        # Floating or TZID times are taken as this computer's local time.
        return datetime.strptime(value, "%Y%m%dT%H%M%S").timestamp()
    except ValueError:
        return None


def parse(text: str) -> list[Event]:
    events: list[Event] = []
    current: dict[str, tuple[str, str]] | None = None
    for line in _unfold(text):
        if line.strip() == "BEGIN:VEVENT":
            current = {}
        elif line.strip() == "END:VEVENT" and current is not None:
            start = _when(*current["DTSTART"]) if "DTSTART" in current else None
            end = _when(*current["DTEND"]) if "DTEND" in current else None
            if start is not None and end is not None and end > start:
                title = current.get("SUMMARY", ("", "(no title)"))[1].replace("\\,", ",")
                events.append(Event(start, end, title.strip() or "(no title)"))
            current = None
        elif current is not None and ":" in line:
            head, value = line.split(":", 1)
            name = head.split(";", 1)[0].upper()
            current[name] = (head, value)
    return events


def import_file(store: Store, path: Path) -> tuple[int, int]:
    """(new, already there) meeting windows from the file."""
    events = parse(path.read_text(encoding="utf-8", errors="replace"))
    new = sum(
        store.add_context(start=e.start, end=e.end, tag="meeting", label=e.title, source="ics")
        for e in events
    )
    return new, len(events) - new
