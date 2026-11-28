"""`mufuse serve` (005 decisions 7-8): the engine on the simulator, then over real HTTP."""

from __future__ import annotations

import http.client
import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from mufuse.acquisition.simulated import Rehearsal, Wearer
from mufuse.companion.serve import VERSION, Engine, Message, Server
from mufuse.companion.store import Store
from mufuse.recording.reader import load_session
from tests.conftest import QUICK, FakeClock

EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "serve_messages"
RESTING = replace(QUICK, resting=True)
RARE = {"observation", "insight"}  # need minutes of baseline; fed directly in their own tests


class Caught:
    """Every message the engine publishes, as an app would receive it."""

    def __init__(self, engine: Engine) -> None:
        self.messages: list[Message] = []
        self._cm = engine.hub.subscribe()
        self._q = self._cm.__enter__()

    def drain(self) -> list[Message]:
        while not self._q.empty():
            m = self._q.get()
            if m is not None:
                self.messages.append(m)
        return self.messages

    def of(self, kind: str) -> list[Message]:
        return [m for m in self.drain() if m["type"] == kind]


def _engine(
    tmp_path: Path, wearer: Wearer = RESTING, record: bool = True
) -> tuple[Engine, FakeClock, Caught]:
    clock = FakeClock()
    rehearsal = Rehearsal(wearer, clock=clock, sleep=clock.advance)
    engine = Engine(
        rehearsal.source,
        Store(tmp_path / "mufuse.db"),
        clock,
        np.random.default_rng(0),
        out=tmp_path / "rec" if record else None,
        mean_wait_s=100.0,  # the decision-2 timings scaled down 15 times: same rules, fewer seconds
        spacing_s=60.0,
    )
    caught = Caught(engine)
    engine.start()
    return engine, clock, caught


def _run(engine: Engine, clock: FakeClock, seconds: float, tick: float = 0.25) -> None:
    for _ in range(round(seconds / tick)):
        clock.advance(tick)
        engine.step()


def test_it_says_hello_then_status_once_a_second_and_features(tmp_path: Path) -> None:
    engine, clock, caught = _engine(tmp_path)
    _run(engine, clock, 20.0)
    assert caught.drain()[0]["type"] == "hello"
    status = caught.of("status")
    assert 18 <= len(status) <= 21
    assert status[-1]["sensors"]["AF7"] == "good"
    assert caught.of("features")
    assert all(m["v"] == VERSION for m in caught.messages)
    engine.stop()


def test_a_random_check_in_comes_and_an_answer_is_stored_by_source(tmp_path: Path) -> None:
    engine, clock, caught = _engine(tmp_path, record=False)
    _run(engine, clock, 4 * 60.0, tick=1.0)
    (first, *_) = caught.of("checkin")
    assert first["source"] == "random"
    assert first["question"] == "What's on your mind?"
    # The first one expired unanswered; ask one more and answer it.
    _run(engine, clock, 1.0)
    while not (
        opened := [
            m
            for m in caught.of("checkin")
            if m["id"] not in {c["id"] for c in caught.of("checkin_closed")}
        ]
    ):
        _run(engine, clock, 10.0, tick=1.0)
    reply = engine.command(
        {"type": "answer", "id": opened[-1]["id"], "answer": opened[-1]["answers"][0]}
    )
    assert reply["type"] == "ok"
    rows = engine.store.checkins(engine.session)
    answered = [r for r in rows if r.answer is not None]
    assert answered[-1].source == "random"
    engine.stop()


def test_a_check_in_left_alone_expires_after_two_minutes(tmp_path: Path) -> None:
    engine, clock, caught = _engine(tmp_path, record=False)
    _run(engine, clock, 5.0)
    assert engine.command({"type": "checkin"})["type"] == "ok"
    _run(engine, clock, 125.0, tick=1.0)
    (closed,) = caught.of("checkin_closed")
    assert closed["answered"] is False
    (row,) = engine.store.checkins(engine.session)
    assert (row.source, row.answer) == ("self", None)
    engine.stop()


def test_commands_mark_snooze_and_focus(tmp_path: Path) -> None:
    engine, clock, caught = _engine(tmp_path)
    _run(engine, clock, 3.0)
    assert engine.command({"type": "mark"})["type"] == "ok"
    assert engine.command({"type": "snooze"})["type"] == "ok"
    assert engine.command({"type": "focus", "on": True})["type"] == "ok"
    _run(engine, clock, 2.0)
    last = caught.of("status")[-1]
    assert last["snoozed"] is True
    assert last["focus"] is True
    assert [m.label for m in engine.store.marks(engine.session)] == ["moment"]
    engine.stop()
    assert engine.writer is not None
    session = load_session(engine.writer.session_dir)
    assert [(m.kind, m.source) for m in session.markers] == [("moment", "app")]


def test_wrong_commands_are_refused_with_a_reason(tmp_path: Path) -> None:
    engine, clock, _ = _engine(tmp_path, record=False)
    _run(engine, clock, 3.0)
    assert engine.command({"type": "dance"})["error"] == "unknown command 'dance'"
    assert engine.command({"type": "answer", "id": 99, "answer": "worry"})["type"] == "error"
    engine.command({"type": "checkin"})
    open_id = engine.status()["open_checkin"]
    assert engine.command({"type": "checkin"})["error"] == "a check-in is already open"
    assert (
        engine.command({"type": "answer", "id": open_id, "answer": "not shown"})["type"] == "error"
    )
    engine.stop()


def test_check_ins_and_answers_land_in_the_recording(tmp_path: Path) -> None:
    engine, clock, caught = _engine(tmp_path)
    _run(engine, clock, 3.0)
    engine.command({"type": "checkin"})
    (asked,) = caught.of("checkin")
    engine.command({"type": "answer", "id": asked["id"], "answer": "planning"})
    engine.stop()
    assert engine.writer is not None
    labels = [m.label for m in load_session(engine.writer.session_dir).markers]
    assert labels == [f"checkin:self:{asked['id']}", f"answer:{asked['id']}:planning"]


def test_with_a_lifted_forehead_the_line_names_the_sensor_and_no_random_check_in_comes(
    tmp_path: Path,
) -> None:
    wearer = replace(RESTING, lifted=((0.0, 1e6, "AF7"), (0.0, 1e6, "AF8")))
    engine, clock, caught = _engine(tmp_path, wearer, record=False)
    _run(engine, clock, 5 * 60.0, tick=1.0)
    assert caught.of("status")[-1]["line"].startswith("fix AF")
    assert caught.of("checkin") == []
    engine.stop()


def _same_shape(message: dict[str, Any], example: dict[str, Any]) -> None:
    assert set(message) == set(example), (message["type"], set(message) ^ set(example))
    for key, value in example.items():
        if value is not None and message[key] is not None:
            assert type(message[key]) is type(value) or {type(value), type(message[key])} <= {
                int,
                float,
            }, key


def test_every_message_has_the_shape_of_its_stored_example(tmp_path: Path) -> None:
    engine, clock, caught = _engine(tmp_path)
    _run(engine, clock, 20.0)
    engine.command({"type": "checkin"})
    (asked,) = caught.of("checkin")
    engine.command({"type": "answer", "id": asked["id"], "answer": asked["answers"][0]})
    engine.stop()
    seen = {m["type"]: m for m in caught.drain()}
    for path in sorted(EXAMPLES.glob("*.json")):
        example = json.loads(path.read_text(encoding="utf-8"))
        if example["type"] in RARE:
            continue  # checked where they can happen: tests/integration/test_observe_serve.py
        assert example["type"] in seen, path.name
        _same_shape(seen[example["type"]], example)
    assert set(seen) <= {
        json.loads(p.read_text(encoding="utf-8"))["type"] for p in EXAMPLES.glob("*.json")
    }


# Over HTTP -------------------------------------------------------------------------------------


@pytest.fixture
def served(tmp_path: Path):
    engine, clock, _ = _engine(tmp_path, record=False)
    _run(engine, clock, 3.0)
    server = Server(engine)
    server.start()
    yield server
    server.stop()
    engine.stop()


def _request(
    server: Server,
    method: str,
    path: str,
    body: object = None,
    *,
    token: str | None = None,
    host: str | None = None,
) -> tuple[int, dict[str, Any]]:
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    headers = {"Host": host or f"127.0.0.1:{server.port}"}
    if token is not False:
        headers["Authorization"] = f"Bearer {token or server.token}"
    data = None if body is None else json.dumps(body).encode()
    if data is not None:
        headers["Content-Type"] = "application/json"
    conn.request(method, path, body=data, headers=headers)
    response = conn.getresponse()
    out = json.loads(response.read() or b"{}")
    conn.close()
    return response.status, out


def test_state_needs_the_token(served: Server) -> None:
    assert _request(served, "GET", "/state")[0] == 200
    assert _request(served, "GET", "/state", token="wrong")[0] == 401


def test_a_request_for_another_host_is_refused(served: Server) -> None:
    code, body = _request(served, "GET", "/state", host="evil.example:80")
    assert (code, body["error"]) == (403, "wrong host")


def test_commands_go_through_http(served: Server) -> None:
    code, body = _request(served, "POST", "/command", {"type": "mark", "label": "idea"})
    assert (code, body["type"]) == (200, "ok")
    assert _request(served, "POST", "/command", {"type": "dance"})[0] == 400
    assert _request(served, "GET", "/nowhere")[0] == 404


def test_an_app_that_goes_away_leaves_no_traceback(
    served: Server, capsys: pytest.CaptureFixture[str]
) -> None:
    httpd = served._httpd  # pyright: ignore[reportPrivateUsage]
    try:
        raise ConnectionResetError("the app closed")
    except ConnectionResetError:
        httpd.handle_error(None, ("127.0.0.1", 1))
    assert capsys.readouterr().err == ""


def test_a_chunked_command_is_read_whole_and_the_connection_stays_usable(served: Server) -> None:
    conn = http.client.HTTPConnection("127.0.0.1", served.port, timeout=5)
    for label in ("one", "two"):  # the second request proves no chunk was left on the line
        body = json.dumps({"type": "mark", "label": label}).encode()
        conn.putrequest("POST", "/command", skip_host=True)
        conn.putheader("Host", f"127.0.0.1:{served.port}")
        conn.putheader("Authorization", f"Bearer {served.token}")
        conn.putheader("Transfer-Encoding", "chunked")
        conn.endheaders()
        half = len(body) // 2
        pieces = (body[:half], body[half:])
        chunks = b"".join(b"%x\r\n%s\r\n" % (len(p), p) for p in pieces)
        conn.send(chunks + b"0\r\n\r\n")
        response = conn.getresponse()
        assert (response.status, json.loads(response.read())["type"]) == (200, "ok")
    conn.close()
    assert [m.label for m in served.engine.store.marks(served.engine.session)] == ["one", "two"]


def test_events_stream_starts_with_hello_and_status(served: Server) -> None:
    conn = http.client.HTTPConnection("127.0.0.1", served.port, timeout=5)
    conn.request(
        "GET", f"/events?token={served.token}", headers={"Host": f"127.0.0.1:{served.port}"}
    )
    response = conn.getresponse()
    assert response.status == 200
    assert response.getheader("Content-Type") == "text/event-stream"
    events: list[str] = []
    while len(events) < 2:
        line = response.readline().decode().strip()
        if line.startswith("event: "):
            events.append(line.removeprefix("event: "))
    assert events == ["hello", "status"]
    conn.close()


def test_the_serve_file_holds_port_and_token(served: Server, tmp_path: Path) -> None:
    path = served.write_serve_file(tmp_path / "state" / "serve.json")
    info = json.loads(path.read_text(encoding="utf-8"))
    assert (info["port"], info["token"], info["v"]) == (served.port, served.token, VERSION)


def test_mufuse_serve_runs_on_the_simulator_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from mufuse.cli import app

    state = tmp_path / "state" / "serve.json"
    monkeypatch.setattr("mufuse.companion.serve.serve_file", lambda: state)
    monkeypatch.setattr(
        "mufuse.companion.store.default_path", lambda: tmp_path / "data" / "mufuse.db"
    )
    result = CliRunner().invoke(
        app, ["serve", "--source", "sim", "--duration", "3", "--out", str(tmp_path / "rec")]
    )
    assert result.exit_code == 0, result.output
    assert "Serving on http://127.0.0.1:" in result.output
    assert "Saved session:" in result.output
    assert not state.exists()  # the token does not outlive the run
    assert (tmp_path / "data" / "mufuse.db").exists()


def test_a_hotkey_mark_is_kept_apart_from_the_strips(tmp_path: Path) -> None:
    engine, clock, _ = _engine(tmp_path)
    _run(engine, clock, 2.0)
    engine.command({"type": "mark"})
    _run(engine, clock, 1.0)
    engine.mark(source="keyboard")
    engine.stop()
    marks = engine.store.marks(engine.session)
    assert [(m.label, m.source) for m in marks] == [("moment", "app"), ("moment", "keyboard")]
    assert engine.writer is not None
    markers = load_session(engine.writer.session_dir).markers
    assert [(m.kind, m.source) for m in markers] == [("moment", "app"), ("moment", "keyboard")]


def test_serve_marks_on_the_hotkey_and_releases_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from mufuse.cli import app
    from mufuse.companion import hotkey

    seen: list[str] = []

    class Pressed:  # presses once as soon as it is registered
        def __init__(self, combo: hotkey.Combo, on_press: Callable[[], None]) -> None:
            self.combo, self.on_press = combo, on_press

        def start(self) -> str | None:
            seen.append(f"start {self.combo.text}")
            self.on_press()
            return None

        def stop(self) -> None:
            seen.append("stop")

    monkeypatch.setattr(hotkey, "Hotkey", Pressed)
    monkeypatch.setattr("mufuse.companion.serve.serve_file", lambda: tmp_path / "serve.json")
    monkeypatch.setattr("mufuse.companion.store.default_path", lambda: tmp_path / "mufuse.db")
    args = [
        "serve",
        "--source",
        "sim",
        "--duration",
        "2",
        "--no-record",
        "--hotkey",
        "ctrl+shift+k",
    ]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert "ctrl+shift+k marks a moment from any window." in result.output
    assert "Marked at 00:00 (ctrl+shift+k)" in result.output
    assert seen == ["start ctrl+shift+k", "stop"]
    store = Store(tmp_path / "mufuse.db")
    ((session, _, _),) = store.sessions()
    assert [m.source for m in store.marks(session)] == ["keyboard"]
    store.close()


@pytest.mark.parametrize(("spec", "code"), [("ctrl+m+n", 2), ("none", 0)])
def test_a_wrong_hotkey_stops_serve_and_none_turns_it_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spec: str, code: int
) -> None:
    from typer.testing import CliRunner

    from mufuse.cli import app

    monkeypatch.setattr("mufuse.companion.serve.serve_file", lambda: tmp_path / "serve.json")
    monkeypatch.setattr("mufuse.companion.store.default_path", lambda: tmp_path / "mufuse.db")
    args = ["serve", "--source", "sim", "--duration", "1", "--no-record", "--hotkey", spec]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == code, result.output
    assert "marks a moment" not in result.output
