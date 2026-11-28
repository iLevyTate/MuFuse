"""008: timeline, calendar import, review page, the serve wiring and the commands."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mufuse.cli import EXIT_BAD_ARGS, EXIT_UNREADABLE, app
from mufuse.companion.store import DEFAULT_ANSWERS, Store
from mufuse.features.engine import FeatureFrame
from mufuse.journal.calendar import import_file, parse
from mufuse.journal.review import render
from mufuse.journal.timeline import timeline
from tests.integration.test_companion_serve import _engine

T0 = datetime(2026, 11, 23, 9, 0, tzinfo=UTC).timestamp()
ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20261123T093000Z
DTEND:20261123T100000Z
SUMMARY:Team sync\\, weekly
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20261124
DTEND;VALUE=DATE:20261125
SUMMARY:Holiday
END:VEVENT
BEGIN:VEVENT
DTSTART:20261123T140000Z
DTEND:20261123T150000Z
SUMMARY:Planning with a very long title that the calendar program folded onto
  a second line
END:VEVENT
END:VCALENDAR
"""
runner = CliRunner()


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "mufuse.db"
    monkeypatch.setattr("mufuse.companion.store.default_path", lambda: path)
    monkeypatch.setattr("mufuse.journal.review.default_dir", lambda: tmp_path / "review")
    return path


def _session(store: Store) -> int:
    s = store.start_session(t=T0)
    c = store.ask(s, t=T0 + 600, source="random", order=DEFAULT_ANSWERS)
    store.answer(c, t=T0 + 605, answer="planning")
    store.ask(s, t=T0 + 1800, source="shift", order=DEFAULT_ANSWERS)
    store.observation_started(s, series="blinks_per_min", direction="higher", t=T0 + 1500)
    store.observation_ended(s, series="blinks_per_min", t=T0 + 1740)
    store.mark(s, t=T0 + 700, label="moment", source="app")
    store.note(t=T0 + 900, text="<b>coffee</b>", tags=["break"], session=s)
    store.end_session(s, t=T0 + 3600)
    return s


def test_the_timeline_holds_every_kind_of_event_in_time_order(tmp_path: Path) -> None:
    store = Store(tmp_path / "db")
    import_file_text = tmp_path / "cal.ics"
    import_file_text.write_text(ICS, encoding="utf-8")
    import_file(store, import_file_text)
    events = timeline(store, _session(store))
    assert [e.t for e in events] == sorted(e.t for e in events)
    texts = [e.text for e in events]
    assert texts[0] == "session started"
    assert "check-in (random): answered 'planning'" in texts
    assert "check-in (shift): not answered" in texts
    assert "blink rate higher than usual for 4 min" in texts
    assert "note: <b>coffee</b> [break]" in texts
    assert any(t.startswith("meeting: Team sync, weekly") for t in texts)
    assert texts[-1] == "session ended"


def test_the_calendar_file_gives_timed_events_and_skips_all_day_ones() -> None:
    events = parse(ICS)
    assert [e.title for e in events] == [
        "Team sync, weekly",
        "Planning with a very long title that the calendar program folded onto a second line",
    ]
    assert events[0].end - events[0].start == 1800


def test_importing_twice_adds_nothing_new(tmp_path: Path) -> None:
    store = Store(tmp_path / "db")
    path = tmp_path / "cal.ics"
    path.write_text(ICS, encoding="utf-8")
    assert import_file(store, path) == (2, 0)
    assert import_file(store, path) == (0, 2)


def test_the_review_page_escapes_what_people_wrote(tmp_path: Path) -> None:
    store = Store(tmp_path / "db")
    _session(store)
    page = render(store, since=T0 - 1, until=T0 + 7200, title="Week")
    assert "&lt;b&gt;coffee&lt;/b&gt;" in page
    assert "<b>coffee</b>" not in page
    assert "hypothesis" in page
    assert "prefers-color-scheme: dark" in page


def test_serve_keeps_observations_and_takes_notes(tmp_path: Path) -> None:
    engine, clock, _ = _engine(tmp_path, record=False)
    for z in [0.0] * 20 + [3.0] * 20 + [0.0] * 30:
        clock.advance(1.0)
        engine._on_frame(FeatureFrame(t=clock.now, values={}, z={"blinks_per_min": z}))  # pyright: ignore[reportPrivateUsage]
    assert engine.command({"type": "note", "text": "felt foggy", "tags": ["sleep"]})["type"] == "ok"
    assert engine.command({"type": "note", "text": "  "})["type"] == "error"
    engine.stop()
    (obs,) = engine.store.observations(session=engine.session)
    assert (obs.series, obs.direction) == ("blinks_per_min", "higher")
    assert obs.end is not None
    (note,) = engine.store.notes()
    assert (note.text, note.tags, note.session) == ("felt foggy", ("sleep",), engine.session)


def test_the_commands_work_end_to_end(db: Path, tmp_path: Path) -> None:
    assert runner.invoke(app, ["timeline"]).exit_code == EXIT_UNREADABLE  # no sessions yet
    store = Store(db)
    session = _session(store)
    store.close()
    assert runner.invoke(app, ["journal", "add", "slept badly", "--tag", "sleep"]).exit_code == 0
    listed = runner.invoke(app, ["journal", "list", "--days", "100000"])
    assert "slept badly  [sleep]" in listed.output
    shown = runner.invoke(app, ["timeline", str(session)])
    assert shown.exit_code == 0, shown.output
    assert "check-in (random): answered 'planning'" in shown.output
    assert runner.invoke(app, ["timeline", "99"]).exit_code == EXIT_BAD_ARGS
    cal = tmp_path / "cal.ics"
    cal.write_text(ICS, encoding="utf-8")
    assert (
        "2 meetings added, 0 already there."
        in runner.invoke(app, ["calendar", "import", str(cal)]).output
    )
    assert (
        runner.invoke(app, ["calendar", "import", str(tmp_path / "nope.ics")]).exit_code
        == EXIT_UNREADABLE
    )
    reviewed = runner.invoke(app, ["review", "--days", "100000"])
    assert reviewed.exit_code == 0, reviewed.output
    assert "hypothesis" in reviewed.output
    assert (tmp_path / "review").is_dir()
