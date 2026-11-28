"""`mufuse serve`: the engine behind a local API for the desk strip (005 decisions 7-8).

`Engine` holds everything that runs (headband, quality, features, check-ins, store, recording)
and is stepped by its caller with an injected clock, so all of it is tested without a network.
`Server` puts it on 127.0.0.1 only: Server-Sent Events out on `GET /events`, commands in on
`POST /command`, a token made fresh each run on every request, and a Host check so a web page
elsewhere cannot reach it through a renamed address. Every message carries `"v": 1`.
"""

from __future__ import annotations

import contextlib
import json
import os
import queue
import secrets
import threading
from collections import deque
from collections.abc import Callable, Generator, Mapping, Sequence
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import numpy as np
from platformdirs import user_state_path

from mufuse.acquisition.source import HeadbandSource
from mufuse.acquisition.supervisor import StreamSupervisor
from mufuse.chat.models import Claude, Model, Ollama
from mufuse.chat.session import ChatSession
from mufuse.chat.summary import Summary
from mufuse.companion.describe import baseline_line
from mufuse.companion.scheduler import MEAN_WAIT_S, SPACING_S, Ask, Conditions, Scheduler
from mufuse.companion.store import Store
from mufuse.features.engine import FeatureEngine, FeatureFrame
from mufuse.observe.interpreters import Interpreter, load_all, window
from mufuse.observe.ledger import counts, review
from mufuse.observe.observations import ObservationDetector, ObservationEvent
from mufuse.quality.answer import FOREHEAD, QualityAnswer
from mufuse.recording.format import Marker
from mufuse.recording.writer import SessionWriter

VERSION = 1
QUESTION = "What's on your mind?"
STATUS_EVERY_S = 1.0
RECENT_S = 120.0  # feature frames kept for the interpreters' windows
INSIGHT_EVERY_S = 15 * 60.0  # at most one insight this often
AFTER_INSIGHT_S = 10 * 60.0  # check-ins this soon after an insight are not evaluated
HEARTBEAT_S = 15.0

Message = dict[str, Any]


def serve_file() -> Path:
    """Where the app finds the port and token of the running engine."""
    return user_state_path("mufuse", appauthor=False) / "serve.json"


# Fan-out to every connected app --------------------------------------------------------------


class Hub:
    """Hands every published message to every subscriber's queue."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: list[queue.Queue[Message | None]] = []

    def publish(self, message: Message) -> None:
        with self._lock:
            for q in self._subscribers:
                q.put(message)

    @contextlib.contextmanager
    def subscribe(self) -> Generator[queue.Queue[Message | None]]:
        q: queue.Queue[Message | None] = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
        try:
            yield q
        finally:
            with self._lock:
                self._subscribers.remove(q)

    def close(self) -> None:
        with self._lock:
            for q in self._subscribers:
                q.put(None)


# The engine ----------------------------------------------------------------------------------


@dataclass
class _Open:
    ask: Ask
    id: int
    order: tuple[str, ...]


@dataclass
class Engine:
    """One serve session. `step()` reads the headband once; `command()` takes one app command."""

    factory: Callable[[], HeadbandSource]
    store: Store
    clock: Callable[[], float]
    rng: np.random.Generator
    out: Path | None = None  # recordings folder; None records nothing
    hub: Hub = field(default_factory=Hub)
    mean_wait_s: float = MEAN_WAIT_S
    spacing_s: float = SPACING_S
    models: Callable[[bool], Sequence[Model]] | None = None  # cloud on? -> models to try, in order

    def __post_init__(self) -> None:
        self._lock = threading.RLock()  # steps run on the main thread, commands on server threads
        self._sup = StreamSupervisor(self.factory, clock=self.clock)
        self._features = FeatureEngine()
        self._answer: QualityAnswer | None = None
        self._frame: FeatureFrame | None = None
        self._focus = False
        self._open: _Open | None = None
        self._last_status = -np.inf
        self._observer = ObservationDetector()
        self._observed_n = 0
        self._interpreters: list[Interpreter] = load_all()
        self._recent: deque[FeatureFrame] = deque()
        self._last_insight = -np.inf
        self._chat = ChatSession(self._chat_models, clock=self.clock)
        self.writer: SessionWriter | None = None
        self.session = 0
        self.started = 0.0

    # Start and stop ----------------------------------------------------------------------------

    def start(self) -> None:
        self._sup.start()
        source = self._sup.source
        assert source is not None
        if self.out is not None:
            self.writer = SessionWriter.create(
                self.out, source.device, source.streams, notes="serve session", clock=self.clock
            )
            self._sup.on_gap_closed = self.writer.add_gap
            self._sup.on_reconnect_step = self.writer.add_reconnect_step
        self.started = self.clock()
        recording = self.writer.session_dir.name if self.writer else None
        self.session = self.store.start_session(t=self.started, recording=recording)
        self._scheduler = Scheduler(
            self.rng, start_t=self.started, mean_wait_s=self.mean_wait_s, spacing_s=self.spacing_s
        )
        for interpreter in self._interpreters:
            review(self.store, interpreter)  # a look reached since the last run is judged now
        self.hub.publish(self.hello())
        self._say(
            "I'm here. Once there is a minute of good signal, I'll describe how it compares"
            " with your own baseline. Ask me anything about it."
        )

    def stop(self) -> None:
        with self._lock:
            now = self.clock()
            if self._open is not None:
                self._close(now, answered=False)
            rows = self.store.checkins(self.session)
            answered = sum(r.answer is not None for r in rows)
            self._say(
                f"Session ended: {answered} of {len(rows)} check-ins answered,"
                f" {self._observed_n} observations. Thanks."
            )
            self.store.end_session(self.session, t=now)
            if self.writer is not None:
                if self._sup.open_gap is not None:
                    self.writer.add_gap(self._sup.open_gap)
                self.writer.finalize(self._sup.lost_subpackets)
            self.hub.publish(self._message("session", state="ended", recording=self._recording))
            self.hub.close()
        with contextlib.suppress(Exception):
            self._sup.stop()

    def _chat_models(self) -> Sequence[Model]:
        cloud = self.store.setting("cloud") == "on"
        if self.models is not None:
            return self.models(cloud)
        return [Claude(), Ollama()] if cloud else [Ollama()]

    def _say(self, text: str) -> None:
        """The chat speaks first (007 decision 6): templates only, never a model."""
        self.hub.publish(
            self._message(
                "chat",
                role="assistant",
                text=text,
                source="template",
                model=None,
                cloud=False,
                t=self.clock(),
            )
        )

    @property
    def _recording(self) -> str | None:
        return self.writer.session_dir.name if self.writer else None

    def _message(self, kind: str, **body: Any) -> Message:
        return {"v": VERSION, "type": kind, **body}

    def hello(self) -> Message:
        source = self._sup.source
        return self._message(
            "hello",
            session=self.session,
            recording=self._recording,
            device=source.device.name if source else None,
            question=QUESTION,
            answers=list(self.store.answers()),
        )

    # One step ----------------------------------------------------------------------------------

    def step(self) -> None:
        chunks = self._sup.poll()
        with self._lock:
            now = self.clock()
            if self.writer is not None:
                self.writer.write(chunks)
            for frame in self._features.feed(chunks):
                self._on_frame(frame)
            self._answer = self._features.latest_answer or self._answer
            if self._open is not None and self._scheduler.expired(now):
                self._close(now, answered=False)
            ask = self._scheduler.tick(now, self.conditions())
            if ask is not None:
                self._ask(ask)
            if now - self._last_status >= STATUS_EVERY_S:
                self._last_status = now
                self.hub.publish(self.status())

    def _on_frame(self, frame: FeatureFrame) -> None:
        self._frame = frame
        self._recent.append(frame)
        while self._recent and self._recent[0].t <= frame.t - RECENT_S:
            self._recent.popleft()
        self.hub.publish(
            self._message("features", t=frame.t, values=dict(frame.values), z=dict(frame.z))
        )
        for event in self._observer.add(frame):
            self._observed(event)
        self._maybe_insight(frame.t)

    def _observed(self, event: ObservationEvent) -> None:
        self.hub.publish(
            self._message(
                "observation",
                state=event.kind,
                series=event.series,
                direction=event.direction,
                since=event.since,
                t=event.t,
                text=event.text,
            )
        )
        if event.kind == "end":
            self.store.observation_ended(self.session, series=event.series, t=event.t)
        if event.kind == "start":
            self.store.observation_started(
                self.session, series=event.series, direction=event.direction, t=event.t
            )
            self._observed_n += 1
            now = self.clock()
            if not self._scheduler.snoozed(now):
                good = self.summary().forehead_good
                self._say(
                    f"{event.text[0].upper()}{event.text[1:]}."
                    f" Signal is good on {good} of 2 forehead sensors."
                )
            ask = self._scheduler.shift(now, self.conditions())
            if ask is not None:
                self._ask(ask)

    def _maybe_insight(self, t: float) -> None:
        """An interpreter's statement, only when promoted or switched on for early feedback."""
        if self._open is not None or t - self._last_insight < INSIGHT_EVERY_S:
            return
        for interpreter in self._interpreters:
            m = interpreter.manifest
            standing = self.store.interpreter(m.id)
            promoted = standing.state == "promoted"
            if not (promoted or standing.early):
                continue
            score = interpreter.score(window(list(self._recent), t, m.window_s))
            if score is None or score < m.threshold:
                continue
            hits, fired = counts(self.store, interpreter)
            self._last_insight = t
            self.hub.publish(
                self._message(
                    "insight",
                    interpreter=m.id,
                    title=m.title,
                    tier=m.tier,
                    early=not promoted,
                    t=t,
                    text=m.say(hits=hits, fired=fired, early=not promoted),
                )
            )
            return

    def summary(self) -> Summary:
        """What the chat may know, made by code (007 decision 4)."""
        with self._lock:
            now = self.clock()
            answer = self._answer
            good = 0 if answer is None else sum(answer.state(s).state == "good" for s in FOREHEAD)
            z = {} if self._frame is None else dict(self._frame.z)
            fix = self._fix()
            rows = [r for r in self.store.checkins(self.session) if r.answer is not None]
            return Summary(
                forehead_good=good,
                fix=fix,
                line=baseline_line(z, fix=fix),
                observations=tuple(
                    (e.text, (now - e.since) / 60.0) for e in self._observer.active.values()
                ),
                last_answer=rows[-1].answer if rows else None,
            )

    def conditions(self) -> Conditions:
        good = self._answer is not None and any(
            self._answer.state(s).state == "good" for s in FOREHEAD
        )
        moving = self._answer is not None and self._answer.movement == "moving"
        return Conditions(signal_good=good, moving=moving, focus=self._focus)

    def _fix(self) -> str | None:
        """The forehead sensor to fix, when neither forehead sensor is good."""
        if self._answer is None:
            return None
        rank = {"none": 0, "noisy": 1, "settling": 2, "good": 3}
        states = {s: self._answer.state(s).state for s in FOREHEAD}
        if any(state == "good" for state in states.values()):
            return None
        return min(FOREHEAD, key=lambda s: rank[states[s]])  # the worst one first

    def status(self) -> Message:
        with self._lock:
            now = self.clock()
            answer = self._answer
            sensors = {} if answer is None else {c.sensor: c.state for c in answer.contact}
            fix = self._fix()
            z = {} if self._frame is None else dict(self._frame.z)
            return self._message(
                "status",
                t=now,
                elapsed=now - self.started,
                link=self._sup.state.value,
                sensors=sensors,
                coverage=None if answer is None else answer.coverage.level,
                moving=answer is not None and answer.movement == "moving",
                focus=self._focus,
                snoozed=self._scheduler.snoozed(now),
                line="waiting for signal" if answer is None else baseline_line(z, fix=fix),
                open_checkin=None if self._open is None else self._open.id,
            )

    # Check-ins ---------------------------------------------------------------------------------

    def _ask(self, ask: Ask) -> None:
        order = ask.order(self.store.answers())
        checkin = self.store.ask(self.session, t=ask.t, source=ask.source, order=order)
        self._open = _Open(ask, checkin, order)
        self._mark_recording(ask.t, f"checkin:{ask.source}:{checkin}")
        frames = list(self._recent)
        for interpreter in self._interpreters:  # shadow mode: every score is kept (006 decision 5)
            m = interpreter.manifest
            score = interpreter.score(window(frames, ask.t, m.window_s))
            self.store.add_score(
                checkin,
                interpreter=m.id,
                version=m.version,
                score=score,
                fired=score is not None and score >= m.threshold,
                after_insight=ask.t - self._last_insight < AFTER_INSIGHT_S,
            )
        self.hub.publish(
            self._message(
                "checkin",
                id=checkin,
                source=ask.source,
                t=ask.t,
                question=QUESTION,
                answers=list(order),
            )
        )

    def _close(self, t: float, *, answered: bool) -> None:
        assert self._open is not None
        if not answered:
            self.store.expire(self._open.id, t=t)
        self.hub.publish(self._message("checkin_closed", id=self._open.id, answered=answered))
        self._open = None
        self._scheduler.close(t)

    def offer_shift(self) -> bool:
        """006 calls this when a signal shifts; True when a check-in was asked."""
        with self._lock:
            ask = self._scheduler.shift(self.clock(), self.conditions())
            if ask is not None:
                self._ask(ask)
            return ask is not None

    def _mark_recording(self, t: float, label: str, source: str = "system") -> None:
        if self.writer is not None:
            if source == "app":
                self.writer.add_marker(Marker(t=t, kind="moment", label=label, source="app"))
            else:
                self.writer.add_marker(Marker(t=t, kind="system", label=label, source="system"))

    # Commands ----------------------------------------------------------------------------------

    def command(self, body: Mapping[str, Any]) -> Message:
        """One command from the app. The reply says `ok` or names what was wrong."""
        kind = body.get("type")
        if kind == "ask":  # outside the lock: a slow model never holds up the headband loop
            return self._ask_cmd(body)
        with self._lock:
            now = self.clock()
            if kind == "mark":
                label = str(body.get("label") or "moment")
                self.store.mark(self.session, t=now, label=label, source="app")
                self._mark_recording(now, label, source="app")
                return self._message("ok", t=now)
            if kind == "checkin":
                if self._open is not None:
                    return self._message("error", error="a check-in is already open")
                self._ask(self._scheduler.self_checkin(now))
                return self._message("ok", t=now)
            if kind == "answer":
                return self._answer_cmd(body, now)
            if kind == "snooze":
                self._scheduler.snooze(now)
                return self._message("ok", t=now)
            if kind == "note":
                text = str(body.get("text") or "").strip()
                if not text:
                    return self._message("error", error="an empty note")
                raw = body.get("tags")
                tags = [str(t) for t in raw] if isinstance(raw, list) else []  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
                self.store.note(t=now, text=text, tags=tags, session=self.session)
                return self._message("ok", t=now)
            if kind == "cloud":
                on = bool(body.get("on"))
                self.store.set_setting("cloud", "on" if on else "off")
                return self._message("ok", t=now, cloud=on)
            if kind == "focus":
                self._focus = bool(body.get("on"))
                return self._message("ok", t=now)
            return self._message("error", error=f"unknown command {kind!r}")

    def _ask_cmd(self, body: Mapping[str, Any]) -> Message:
        text = str(body.get("text") or "").strip()
        if not text:
            return self._message("error", error="nothing asked")
        reply = self._chat.ask(text, self.summary())
        message = self._message(
            "chat",
            role="assistant",
            text=reply.text,
            source=reply.source,
            model=reply.model,
            cloud=reply.cloud,
            t=self.clock(),
        )
        self.hub.publish(message)
        return {**message, "type": "ok", "reply": reply.text}

    def _answer_cmd(self, body: Mapping[str, Any], now: float) -> Message:
        if self._open is None or body.get("id") != self._open.id:
            return self._message("error", error="no such open check-in")
        answer = body.get("answer")
        if answer not in self._open.order:
            return self._message("error", error="not one of the answers shown")
        text = body.get("text")
        said = None if text is None else str(text)
        self.store.answer(self._open.id, t=now, answer=str(answer), text=said)
        self._mark_recording(now, f"answer:{self._open.id}:{answer}")
        self._close(now, answered=True)
        self._say(f"Noted: {answer}.")
        return self._message("ok", t=now)


# The HTTP layer ------------------------------------------------------------------------------


class Server:
    """The engine on 127.0.0.1, on a free port, behind a token made fresh for this run."""

    def __init__(self, engine: Engine, *, port: int = 0, token: str | None = None) -> None:
        self.engine = engine
        self.token = token or secrets.token_urlsafe(24)
        self._httpd = ThreadingHTTPServer(("127.0.0.1", port), _handler(self))
        self._httpd.daemon_threads = True
        self.port = int(self._httpd.server_address[1])
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self.engine.hub.close()
        self._httpd.shutdown()
        self._httpd.server_close()

    def write_serve_file(self, path: Path | None = None) -> Path:
        path = path or serve_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        info = {"v": VERSION, "port": self.port, "token": self.token, "pid": os.getpid()}
        path.write_text(json.dumps(info), encoding="utf-8")
        with contextlib.suppress(OSError):
            path.chmod(0o600)  # the token is for this user only
        return path


def _handler(server: Server) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:
            pass  # requests carry the token; nothing about them is logged

        def _allowed(self) -> bool:
            allowed_hosts = {f"127.0.0.1:{server.port}", f"localhost:{server.port}"}
            if self.headers.get("Host") not in allowed_hosts:
                self._reply(403, {"v": VERSION, "type": "error", "error": "wrong host"})
                return False
            query = parse_qs(urlparse(self.path).query)
            given = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            given = given or (query.get("token") or [""])[0]
            if not secrets.compare_digest(given, server.token):
                self._reply(401, {"v": VERSION, "type": "error", "error": "token"})
                return False
            return True

        def _reply(self, code: int, body: Message) -> None:
            data = json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if not self._allowed():
                return
            route = urlparse(self.path).path
            if route == "/state":
                self._reply(200, {**server.engine.status(), "hello": server.engine.hello()})
            elif route == "/events":
                self._events()
            else:
                self._reply(404, {"v": VERSION, "type": "error", "error": "not found"})

        def do_POST(self) -> None:
            if not self._allowed():
                return
            if urlparse(self.path).path != "/command":
                self._reply(404, {"v": VERSION, "type": "error", "error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, json.JSONDecodeError):
                self._reply(400, {"v": VERSION, "type": "error", "error": "not JSON"})
                return
            if not isinstance(body, dict):
                self._reply(400, {"v": VERSION, "type": "error", "error": "not an object"})
                return
            reply = server.engine.command(body)  # pyright: ignore[reportUnknownArgumentType]
            self._reply(200 if reply["type"] == "ok" else 400, reply)

        def _events(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            with server.engine.hub.subscribe() as q:
                try:
                    self._send(server.engine.hello())
                    self._send(server.engine.status())
                    while True:
                        try:
                            message = q.get(timeout=HEARTBEAT_S)
                        except queue.Empty:
                            self.wfile.write(b": still here\n\n")
                            self.wfile.flush()
                            continue
                        if message is None:
                            return
                        self._send(message)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return

        def _send(self, message: Message) -> None:
            self.wfile.write(f"event: {message['type']}\ndata: {json.dumps(message)}\n\n".encode())
            self.wfile.flush()

    return Handler
