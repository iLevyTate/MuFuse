"""MuFuse command-line interface: devices, stream, record, inspect, features, serve, chat, ..."""

from __future__ import annotations

import contextlib
import io
import math
import os
import signal
import sys
import threading
import time
from collections.abc import Callable, Generator
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from types import FrameType
from typing import Annotated

import typer
from rich.console import Console, RenderableType
from rich.live import Live

from mufuse.acquisition.athena import DEFAULT_PRESET, preset_warning, validate_preset
from mufuse.acquisition.source import HeadbandSource
from mufuse.acquisition.supervisor import StreamSupervisor
from mufuse.acquisition.types import SourceError, StreamKind
from mufuse.banner import print_banner
from mufuse.config import load_config, save_config
from mufuse.exercises.breathe import (
    DEFAULT_MINUTES,
    DEFAULT_RATE,
    BreatheReport,
    breathe_guide,
    measure,
)
from mufuse.exercises.breathe import rehearsal_wearer as breathe_wearer
from mufuse.exercises.breathe import report_lines as breathe_lines
from mufuse.exercises.library import load as load_exercise
from mufuse.fnirs.protocol import FnirsScore
from mufuse.guide import Guide, guide_from_env
from mufuse.keys import KeyPoller
from mufuse.live_view import YELLOW, LiveStats, Screen, render
from mufuse.preflight import START_KEYS, Preflight
from mufuse.quality.answer import SessionQuality
from mufuse.quality.engine import judge
from mufuse.quality.labelled import (
    RUN_S,
    ScoreReport,
    cues_from_markers,
    labelled_guide,
    rehearsal_wearer,
    report_lines,
    score,
)
from mufuse.quality.summary import summarize, summary_lines
from mufuse.recording.format import Marker
from mufuse.recording.reader import LoadedSession, load_session
from mufuse.recording.writer import SessionWriter
from mufuse.runlog import ConnectRun, TimeToSignal, append_run
from mufuse.sound import tone

app = typer.Typer(
    no_args_is_help=True, help="MuFuse: Punk EEG. Muse S Athena acquisition and recording."
)
console = Console()

EXIT_BAD_ARGS, EXIT_NONE_FOUND, EXIT_CONNECT, EXIT_WRITE, EXIT_UNREADABLE = 2, 3, 4, 5, 6
EXIT_INTERRUPTED = 130  # Ctrl+C before anything was shown or recorded
STATUS_EVERY_S = 5.0  # how often output that is not a terminal gets a status line


class SourceKind(StrEnum):
    athena = "athena"
    sim = "sim"
    play = "play"


SourceOpt = Annotated[
    SourceKind, typer.Option(help="athena = headband, sim = simulated, play = replay")
]
DeviceOpt = Annotated[str | None, typer.Option(help="Headband name, e.g. MuseS-1A2B")]
PresetOpt = Annotated[str, typer.Option(help="Athena device preset")]
PlayOpt = Annotated[Path | None, typer.Option(help="Session folder for --source play")]
DurationOpt = Annotated[float | None, typer.Option(help="Stop after N seconds")]


def use_utf8_output() -> None:
    """Piped or redirected output on Windows uses a legacy code page that cannot encode ✓ or ≥."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")


@app.callback()
def _main() -> None:  # pyright: ignore[reportUnusedFunction]
    use_utf8_output()


def _source_factory(
    source: SourceKind, device: str | None, preset: str, play: Path | None
) -> tuple[Callable[[], HeadbandSource], Callable[[], str | None]]:
    """How to connect to the chosen source, and where key presses come from while it runs."""
    try:
        validate_preset(preset)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(EXIT_BAD_ARGS) from exc
    if source is SourceKind.sim:
        from mufuse.acceptance import wearer_from_env
        from mufuse.acquisition.simulated import Rehearsal, SimulatedAthena

        try:
            wearer = wearer_from_env()
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(EXIT_BAD_ARGS) from exc
        if wearer is None:
            return (lambda: SimulatedAthena(preset=preset)), _read_key
        # A hardware check rehearsed without the headband: the scripted wearer presses the
        # keys, and the real keyboard still works.
        rehearsal = Rehearsal(wearer, preset=preset)
        return rehearsal.source, lambda: rehearsal.read_key() or _read_key()
    if source is SourceKind.play:
        if play is None:
            console.print("[red]--play PATH is required with --source play[/red]")
            raise typer.Exit(EXIT_BAD_ARGS)
        from mufuse.acquisition.playback import PlaybackSource

        return (lambda: PlaybackSource(play)), _read_key
    from mufuse.acquisition.brainflow_athena import BrainFlowAthena

    name = device or _remembered_or_scanned_device()
    return (lambda: BrainFlowAthena(device_name=name, preset=preset)), _read_key


def _remembered_or_scanned_device() -> str | None:
    config = load_config()
    if config.last_device_name:
        return config.last_device_name
    from mufuse.acquisition.discovery import scan_for_muse

    console.print("Scanning for Muse headbands…")
    found = scan_for_muse(timeout_s=6.0)
    if not found:
        return None  # let the driver try the first device it sees
    config.last_device_name, config.last_device_address = found[0].name, found[0].address
    save_config(config)
    console.print(f"Using {found[0].name} (saved for next time)")
    return found[0].name


@dataclass(frozen=True)
class _Attempt:
    """What the connection log needs to know about this command."""

    command: str
    source: SourceKind
    preset: str
    t0: float

    @classmethod
    def begin(cls, command: str, source: SourceKind, preset: str) -> _Attempt:
        # A launcher (scripts/h3_time_to_signal.py) passes its own start so startup time counts.
        raw = os.environ.get("MUFUSE_T0", "")
        try:
            t0 = float(raw) if raw else time.time()
        except ValueError:
            t0 = time.time()
        return cls(command, source, preset, t0)

    @property
    def slow(self) -> bool:
        """The headband takes seconds to connect and to let go, and so does a rehearsed one:
        both waits are announced, so the screen never stands still without a reason."""
        return self.source is SourceKind.athena or bool(os.environ.get("MUFUSE_SIM_WEARER"))

    def log(
        self, outcome: str, seconds: float | None, device: str | None, error: str | None = None
    ) -> None:
        append_run(
            ConnectRun(
                at=datetime.fromtimestamp(self.t0).isoformat(timespec="seconds"),
                command=self.command,
                source=self.source.value,
                device=device,
                preset=self.preset,
                outcome=outcome,
                seconds_to_signal=None if seconds is None else round(seconds, 3),
                elapsed_s=round(time.time() - self.t0, 3),
                error=error,
                label=os.environ.get("MUFUSE_RUN_LABEL") or None,
            )
        )


_KEYS = KeyPoller()  # opened by stream and record, so POSIX terminals hand keys over at once


def _read_key() -> str | None:
    return _KEYS.poll()


@contextlib.contextmanager
def _stop_on_ctrl_c() -> Generator[threading.Event]:
    """Ctrl+C sets a flag instead of raising, so it cannot land in saving or in the release."""
    stop = threading.Event()
    if threading.current_thread() is not threading.main_thread():
        yield stop  # signal handlers belong to the main thread
        return

    def on_ctrl_c(signum: int, frame: FrameType | None) -> None:
        stop.set()

    previous = signal.signal(signal.SIGINT, on_ctrl_c)
    try:
        yield stop
    finally:
        signal.signal(signal.SIGINT, signal.default_int_handler if previous is None else previous)


def _run(
    attempt: _Attempt,
    factory: Callable[[], HeadbandSource],
    duration: float | None,
    writer_factory: Callable[[HeadbandSource], SessionWriter] | None = None,
    *,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
    read_key: Callable[[], str | None] = _read_key,
    stats: LiveStats | None = None,
    guide: Guide | None = None,
    preflight: Preflight | None = None,
    on_start: Callable[[], None] | None = None,
) -> None:
    """`stats`, when given, keeps what the live view judged (for the replay check); `guide`
    replaces the one a launcher hands over in MUFUSE_GUIDE; `preflight` checks the fit before
    the guide's clock starts, and `on_start` is called the moment it does."""
    sup = StreamSupervisor(factory, clock=clock)
    with _stop_on_ctrl_c() as stop:
        if attempt.slow:
            console.print(
                "Connecting to the headband: usually about 5 s, up to 20 s if it is not found. "
                "Nothing to press."
            )
        try:
            sup.start()
        except SourceError as exc:
            attempt.log("connect_error", None, None, str(exc))
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(EXIT_CONNECT) from exc
        assert sup.source is not None
        device = sup.source.device
        if stop.is_set():  # Ctrl+C while connecting: the driver only hands it over afterwards
            console.print("Stopped before it began. Nothing was recorded.")
            attempt.log("interrupted", None, device.name)
            _release(attempt, sup)
            raise typer.Exit(EXIT_INTERRUPTED)
        timer = TimeToSignal(attempt.t0)
        firmware = f" · fw {device.firmware}" if device.firmware else ""
        print_banner(console, f"{device.name}{firmware} · preset {device.preset}")
        warning = preset_warning(device.preset, device.extra.get("active_preset"))
        if warning is not None:
            console.print(f"! {warning}", style=YELLOW)
        try:
            _show_and_record(
                sup,
                timer,
                duration,
                writer_factory,
                stop,
                clock,
                sleep,
                read_key,
                stats,
                guide,
                preflight,
                on_start,
            )
        except OSError as exc:
            console.print(f"[red]Write error: {exc}[/red]")
            raise typer.Exit(EXIT_WRITE) from exc
        finally:
            # The session is saved by now. The log comes next: the release is slow, and nothing
            # that happens during it may cost the evidence.
            try:
                outcome = "no_signal" if timer.seconds is None else "signal"
                attempt.log(outcome, timer.seconds, device.name)
            finally:
                _release(attempt, sup)


def _show_and_record(
    sup: StreamSupervisor,
    timer: TimeToSignal,
    duration: float | None,
    writer_factory: Callable[[HeadbandSource], SessionWriter] | None,
    stop: threading.Event,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
    read_key: Callable[[], str | None],
    stats: LiveStats | None = None,
    guide: Guide | None = None,
    preflight: Preflight | None = None,
    on_start: Callable[[], None] | None = None,
) -> None:
    """The live loop. Whatever ends it, the session is finalized before this returns."""
    assert sup.source is not None
    writer = writer_factory(sup.source) if writer_factory else None
    try:
        if writer is not None:
            sup.on_gap_closed = writer.add_gap
            sup.on_reconnect_step = writer.add_reconnect_step
        recording = writer.session_dir.name if writer else None
        guide = guide or guide_from_env()
        stats = LiveStats(clock) if stats is None else stats
        open_blocks, markers = set[str](), 0
        latest: list[Screen] = [render(sup, stats, recording)]
        while read_key() is not None:  # keys typed while it was connecting are not for this run
            pass
        began = clock()
        # What the guide panel shows and since when: the pre-flight check first, if there is one.
        shown: list[tuple[Guide | None, float]] = [
            (preflight.guide(deciding=False), began) if preflight else (guide, began)
        ]

        def view() -> RenderableType:
            # Runs on Live's refresh thread, so the clocks keep moving even while a reconnect
            # attempt blocks the loop below.
            panel, since = shown[0]
            return latest[0].with_time(clock() - began, panel, clock() - since)

        # A terminal gets the redrawn view; piped or redirected output gets a status line now
        # and then, since a redrawn panel would only reach it when the run ends.
        display = (
            Live(console=console, refresh_per_second=4, get_renderable=view)
            if console.is_terminal
            else contextlib.nullcontext()
        )
        last_status = -math.inf
        with display:
            if preflight is not None:
                go = _preflight(sup, stats, writer, preflight, stop, clock, sleep, read_key, shown)
                if not go:
                    return
            started = clock()
            shown[0] = (guide, started)
            if on_start is not None:
                on_start()
            # The time limit is checked before every poll, so no reconnect attempt begins
            # after it has passed.
            while not stop.is_set() and (duration is None or clock() - started < duration):
                chunks = sup.poll()
                now = clock()
                stats.add(chunks, now)
                if (seconds := timer.observe(chunks, now)) is not None:
                    console.print(f"first EEG after {seconds:.1f} s")
                if writer is not None:
                    writer.write(chunks)
                    for label, offset in guide.due(now - started) if guide else []:
                        t = started + offset
                        writer.add_marker(Marker(t=t, kind="system", label=label, source="system"))
                if guide is not None and guide.bells(now - started):
                    console.bell()
                    tone()  # the terminal may answer the bell with nothing
                key = read_key()
                if key == "q":
                    break
                if writer is not None and (marker := _key_marker(key, open_blocks, now)):
                    writer.add_marker(marker)
                    markers += 1
                latest[0] = render(sup, stats, recording, markers, elapsed=now - began)
                if not console.is_terminal and now - last_status >= STATUS_EVERY_S:
                    _status(latest[0], clock() - started, guide)
                    last_status = now
                sleep(0.05)
            if not console.is_terminal:  # how it ended, as the redrawn view would have shown it
                _status(latest[0], clock() - started, guide)
    finally:
        if stats is not None:
            stats.finish()  # the last stretches, judged with the samples that exist
        gap = sup.open_gap  # read before the supervisor is stopped
        if writer is not None:
            if gap is not None:
                writer.add_gap(gap)
            writer.finalize(sup.lost_subpackets)
            console.print(f"Saved session: {writer.session_dir}")
        if gap is not None:
            console.print(
                "[yellow]Stopped before the signal returned. The gap is saved as open.[/yellow]"
            )


def _preflight(
    sup: StreamSupervisor,
    stats: LiveStats,
    writer: SessionWriter | None,
    check: Preflight,
    stop: threading.Event,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
    read_key: Callable[[], str | None],
    shown: list[tuple[Guide | None, float]],
) -> bool:
    """Wait for a good fit before the guide starts. True: go on; False: the wearer stopped.

    The samples of the check are recorded like any other, so the session shows the fitting too.
    Nothing here stops the run on its own: past the wait, the wearer decides.
    """
    began, deciding = clock(), False
    while not stop.is_set():
        chunks = sup.poll()
        now = clock()
        stats.add(chunks, now)
        if writer is not None:
            writer.write(chunks)
        sensors, motion = stats.contact(), stats.rate(StreamKind.MOTION) > 0
        phase = check.phase(sensors, motion=motion, elapsed=now - began)
        key = read_key()
        if key == "q":
            console.print("Stopped at the pre-flight check.")
            return False
        if phase == "ready" or key in START_KEYS:
            anyway = phase != "ready"
            for line in check.outcome(sensors, motion=motion, anyway=anyway):
                console.print(line, markup=False, highlight=False)
            if writer is not None:
                label = check.marker(sensors, anyway=anyway)
                writer.add_marker(Marker(t=now, kind="system", label=label, source="system"))
            return True
        if phase == "decide" and not deciding:
            deciding = True
            shown[0] = (check.guide(deciding=True), now)
            if not console.is_terminal:
                console.print("Pre-flight: forehead not good yet. s = start anyway, q = stop.")
        sleep(0.05)
    return False


def _status(screen: Screen, elapsed: float, guide: Guide | None) -> None:
    line = screen.with_time(elapsed, guide, elapsed).status_line()
    console.print(line, markup=False, highlight=False, soft_wrap=True)


def _release(attempt: _Attempt, sup: StreamSupervisor) -> None:
    """Let go of the headband. Nothing depends on how this ends."""
    if attempt.slow:
        console.print("Releasing the headband, about 8 s. Nothing to press.")
    try:
        sup.stop()
    except Exception as exc:
        console.print(f"[yellow]The headband was not released cleanly: {exc}[/yellow]")


def _key_marker(key: str | None, open_blocks: set[str], now: float) -> Marker | None:
    """The marker a key stands for, if any: space = a moment, 1-9 = start or end a block."""
    if key == " ":
        return Marker(t=now, kind="moment", label="moment", source="keyboard")
    if key is not None and key.isdigit() and key != "0":
        label = f"block {key}"
        kind = "block_end" if label in open_blocks else "block_start"
        open_blocks.symmetric_difference_update({label})
        return Marker(t=now, kind=kind, label=label, source="keyboard")
    return None


@app.command()
def devices(timeout: float = 8.0) -> None:
    """Scan for nearby Muse headbands."""
    from mufuse.acquisition.discovery import scan_for_muse

    found = scan_for_muse(timeout)
    if not found:
        console.print("No Muse found. Is it on, and is the Muse app closed?")
        raise typer.Exit(EXIT_NONE_FOUND)
    saved = load_config().last_device_name
    for d in found:
        console.print(
            f"{d.name}  {d.address}  RSSI {d.rssi}" + ("  (saved)" if d.name == saved else "")
        )


@app.command()
def stream(
    source: SourceOpt = SourceKind.athena,
    device: DeviceOpt = None,
    preset: PresetOpt = DEFAULT_PRESET,
    play: PlayOpt = None,
    duration: DurationOpt = None,
) -> None:
    """Show live signal from the headband (q or Ctrl+C to stop)."""
    attempt = _Attempt.begin("stream", source, preset)
    factory, read_key = _source_factory(source, device, preset, play)
    with _KEYS:
        _run(attempt, factory, duration, read_key=read_key)


@app.command()
def record(
    source: SourceOpt = SourceKind.athena,
    device: DeviceOpt = None,
    preset: PresetOpt = DEFAULT_PRESET,
    play: PlayOpt = None,
    duration: DurationOpt = None,
    notes: Annotated[str, typer.Option(help="What you are doing")] = "",
    out: Annotated[Path, typer.Option(help="Recordings folder")] = Path("recordings"),
) -> None:
    """Record a session with keyboard markers."""
    attempt = _Attempt.begin("record", source, preset)
    factory, read_key = _source_factory(source, device, preset, play)
    with _KEYS:
        _run(
            attempt,
            factory,
            duration,
            lambda src: SessionWriter.create(out, src.device, src.streams, notes=notes),
            read_key=read_key,
        )


@app.command()
def inspect(path: Path) -> None:
    """Summarize a recorded session."""
    try:
        session = load_session(path)
    except (OSError, ValueError, KeyError) as exc:
        console.print(f"[red]Cannot read session: {exc}[/red]")
        raise typer.Exit(EXIT_UNREADABLE) from exc
    m = session.manifest
    status = "finalized" if session.finalized else "NOT finalized (interrupted)"
    console.print(
        f"[bold]{m['session_id']}[/bold]  {status}  device={m['device']['name']} "
        f"fw={m['device'].get('firmware') or '?'}  preset={m['device']['preset']}  "
        f"notes={m['notes']!r}"
    )
    for kind, (ts, _) in session.streams.items():
        span = ts[-1] - ts[0] if ts.size > 1 else 0.0
        completeness: dict[str, dict[str, int]] = m["completeness"] or {}
        comp = completeness.get(kind.value)
        pct = (
            f"{100 * comp['received'] / comp['expected']:.2f}%"
            if comp and comp["expected"]
            else "—"
        )
        console.print(f"  {kind.value:<7} {ts.size:>9} samples  {span:8.1f} s  complete {pct}")
    console.print(f"  markers: {len(session.markers)}  gaps: {len(session.gaps)}")
    lost: dict[str, int] | None = m.get("lost_subpackets")
    if lost is not None:
        counts = "  ".join(f"{kind} {n}" for kind, n in lost.items())
        console.print(f"  subpackets lost on the headset link: {counts}")
    for g in session.gaps:
        dur = f"{g.end - g.start:.2f} s" if g.end is not None else "open"
        console.print(f"    gap {g.reason} {dur}")
    try:
        quality = summarize(judge(session))
    except ValueError as exc:  # samples out of order: the summary cannot be made
        console.print(f"Signal quality: not available ({exc})", markup=False, highlight=False)
        return
    for line in summary_lines(quality):
        console.print(line, markup=False, highlight=False)


@app.command()
def features(
    path: Annotated[Path, typer.Argument(help="A recorded session folder")],
    csv_out: Annotated[
        Path | None, typer.Option("--csv", help="Also write one row per second to this file")
    ] = None,
) -> None:
    """EEG and pulse features of a recorded session, each second against your own baseline."""
    from mufuse.features.engine import extract
    from mufuse.features.report import summary_lines, write_csv

    try:
        session = load_session(path)
    except (OSError, ValueError, KeyError) as exc:
        console.print(f"[red]Cannot read session: {exc}[/red]")
        raise typer.Exit(EXIT_UNREADABLE) from exc
    frames = extract(session)
    for line in summary_lines(frames):
        console.print(line, markup=False, highlight=False)
    if csv_out is not None:
        write_csv(frames, csv_out)
        console.print(f"Wrote {len(frames)} rows: {csv_out}", markup=False, highlight=False)


@app.command()
def serve(
    source: SourceOpt = SourceKind.athena,
    device: DeviceOpt = None,
    preset: PresetOpt = DEFAULT_PRESET,
    play: PlayOpt = None,
    out: Annotated[Path, typer.Option(help="Recordings folder")] = Path("recordings"),
    record: Annotated[bool, typer.Option(help="Record the session while serving")] = True,
    duration: DurationOpt = None,
) -> None:
    """Run the engine for the desk strip: check-ins, features, on this computer only."""
    import numpy as np

    from mufuse.companion.serve import Engine, Server
    from mufuse.companion.store import Store

    factory, _ = _source_factory(source, device, preset, play)
    store = Store()
    engine = Engine(factory, store, time.time, np.random.default_rng(), out=out if record else None)
    try:
        engine.start()
    except SourceError as exc:
        console.print(f"[red]{exc}[/red]")
        store.close()
        raise typer.Exit(EXIT_CONNECT) from exc
    server = Server(engine)
    server.start()
    info = server.write_serve_file()
    console.print(
        f"Serving on http://127.0.0.1:{server.port} (this computer only; token in {info}).",
        markup=False,
        highlight=False,
    )
    console.print("Start the desk strip now. Ctrl+C stops.", markup=False, highlight=False)
    try:
        _serve_loop(engine, duration)
    finally:
        server.stop()
        engine.stop()
        store.close()
        with contextlib.suppress(OSError):
            info.unlink()
        if engine.writer is not None:
            console.print(f"Saved session: {engine.writer.session_dir}", markup=False)


def _serve_loop(
    engine: object,
    duration: float | None,
    *,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    from mufuse.companion.serve import Engine

    assert isinstance(engine, Engine)
    started, last = clock(), -math.inf
    with _stop_on_ctrl_c() as stop:
        while not stop.is_set() and (duration is None or clock() - started < duration):
            engine.step()
            now = clock()
            if now - last >= STATUS_EVERY_S:
                last = now
                s = engine.status()
                line = f"{_mmss(now - started)}  {s['link']}  {s['line']}"
                console.print(line, markup=False, highlight=False)
            sleep(0.05)


def _mmss(seconds: float) -> str:
    whole = max(int(seconds), 0)
    return f"{whole // 60:02d}:{whole % 60:02d}"


@app.command()
def chat(
    cloud: Annotated[
        bool | None,
        typer.Option("--cloud/--local", help="Let the Claude API word replies (summary only)"),
    ] = None,
) -> None:
    """Chat with the running engine (`mufuse serve`) in this terminal. An empty line ends it."""
    from mufuse.chat.client import ChatClient, EngineNotRunningError

    try:
        client = ChatClient.from_serve_file()
    except EngineNotRunningError as exc:
        console.print(str(exc), markup=False, highlight=False)
        raise typer.Exit(EXIT_CONNECT) from exc
    if cloud is not None:
        try:
            client.cloud(cloud)
        except EngineNotRunningError as exc:
            console.print(str(exc), markup=False, highlight=False)
            raise typer.Exit(EXIT_CONNECT) from exc
        state = "on: replies may be worded by the Claude API" if cloud else "off"
        console.print(f"Cloud {state}.", markup=False, highlight=False)
    console.print("Ask what the signal is doing. An empty line ends the chat.", markup=False)
    while True:
        try:
            text = input("> ").strip()
        except EOFError:
            break
        if not text:
            break
        try:
            reply = client.ask(text)
        except EngineNotRunningError as exc:
            console.print(str(exc), markup=False, highlight=False)
            raise typer.Exit(EXIT_CONNECT) from exc
        badge = " [cloud]" if reply.get("cloud") else ""
        console.print(f"{reply.get('reply', reply.get('error'))}{badge}", markup=False)


# mufuse journal / timeline / calendar / review (008) ------------------------------------------

journal_app = typer.Typer(no_args_is_help=True, help="Your own notes, kept on this computer.")
app.add_typer(journal_app, name="journal")
calendar_app = typer.Typer(no_args_is_help=True, help="Meetings from a calendar file (.ics).")
app.add_typer(calendar_app, name="calendar")


@journal_app.command("add")
def journal_add(
    text: Annotated[str, typer.Argument(help="The note")],
    tag: Annotated[list[str] | None, typer.Option(help="A tag; repeat for more")] = None,
) -> None:
    """Add a note to the journal."""
    from mufuse.companion.store import Store

    store = Store()
    try:
        store.note(t=time.time(), text=text, tags=tag or [])
    finally:
        store.close()
    console.print("Noted.", markup=False)


@journal_app.command("list")
def journal_list(days: Annotated[float, typer.Option(help="How far back")] = 7.0) -> None:
    """The notes of the last days."""
    from mufuse.companion.store import Store

    store = Store()
    try:
        notes = store.notes(since=time.time() - days * 86400)
    finally:
        store.close()
    if not notes:
        console.print("No notes yet.", markup=False)
    for n in notes:
        when = datetime.fromtimestamp(n.t).strftime("%a %d %b %H:%M")
        tags = f"  [{', '.join(n.tags)}]" if n.tags else ""
        console.print(f"{when}  {n.text}{tags}", markup=False, highlight=False)


@app.command()
def timeline(
    session: Annotated[
        int | None, typer.Argument(help="Session number; the newest if left out")
    ] = None,
) -> None:
    """One serve session as a timeline: check-ins, observations, marks, notes, meetings."""
    from mufuse.companion.store import Store
    from mufuse.journal.timeline import timeline as make
    from mufuse.journal.timeline import timeline_lines

    store = Store()
    try:
        sessions = store.sessions()
        if not sessions:
            console.print("No sessions yet: run `mufuse serve` first.", markup=False)
            raise typer.Exit(EXIT_UNREADABLE)
        chosen = session if session is not None else sessions[-1][0]
        try:
            events = make(store, chosen)
        except KeyError as exc:
            console.print(f"No session {chosen}.", markup=False)
            raise typer.Exit(EXIT_BAD_ARGS) from exc
    finally:
        store.close()
    for line in timeline_lines(events):
        console.print(line, markup=False, highlight=False)


@calendar_app.command("import")
def calendar_import(
    path: Annotated[Path, typer.Argument(help="An .ics file you exported")],
) -> None:
    """Store the file's events as meeting windows (read once; no account, no network)."""
    from mufuse.companion.store import Store
    from mufuse.journal.calendar import import_file

    store = Store()
    try:
        new, known = import_file(store, path)
    except OSError as exc:
        console.print(f"Cannot read {path}: {exc}", markup=False)
        raise typer.Exit(EXIT_UNREADABLE) from exc
    finally:
        store.close()
    console.print(f"{new} meetings added, {known} already there.", markup=False)


@app.command()
def review(
    days: Annotated[float, typer.Option(help="How far back")] = 7.0,
    out: Annotated[Path | None, typer.Option(help="Write the page here")] = None,
) -> None:
    """The weekly reflection: patterns (n, effect, hypothesis) and a review page on disk."""
    from mufuse.companion.store import Store
    from mufuse.journal import review as page
    from mufuse.journal.patterns import find, pattern_lines

    now = time.time()
    store = Store()
    try:
        for line in pattern_lines(find(store, since=now - days * 86400, until=now)):
            console.print(line, markup=False, highlight=False)
        path = page.write(store, since=now - days * 86400, until=now, out=out)
    finally:
        store.close()
    console.print(f"Review page: {path}", markup=False, highlight=False)


# mufuse interpreters --------------------------------------------------------------------------

interpreters_app = typer.Typer(help="Interpreters: shadow mode, hit rates, early feedback (006).")
app.add_typer(interpreters_app, name="interpreters")


def _pct(x: float | None) -> str:
    return "-" if x is None else f"{100 * x:.0f}%"


@interpreters_app.callback(invoke_without_command=True)
def interpreters_list(ctx: typer.Context) -> None:
    """Each interpreter's standing on your own random check-ins."""
    if ctx.invoked_subcommand is not None:
        return
    from mufuse.companion.store import Store
    from mufuse.observe.interpreters import load_all
    from mufuse.observe.ledger import review

    store = Store()
    try:
        for interpreter in load_all():
            standing = review(store, interpreter)
            m, e = interpreter.manifest, standing.verdict.evaluation
            early = "on" if standing.state.early else "off"
            auc = "-" if e.auc is None else f"{e.auc:.2f}"
            p = "-" if e.p is None else f"{e.p:.3f}"
            lines = [
                f"{m.id} v{m.version} ({m.title}, {m.tier}): {standing.state.state},"
                f" early feedback {early}",
                f"  random answers scored {e.n}, next look at {standing.next_look}",
                f"  base rate {_pct(e.base_rate)}  hit rate {_pct(e.hit_rate)}"
                f" (fired {e.fired})  AUC {auc}  p {p}",
            ]
            if e.n < m.looks[0]:
                lines.append("  not yet known: it is judged at its looks only")
            for line in lines:
                console.print(line, markup=False, highlight=False)
    finally:
        store.close()


@interpreters_app.command("feedback")
def interpreters_feedback(
    state: Annotated[str, typer.Argument(help="on or off")],
    id_: Annotated[
        str | None, typer.Option("--id", help="One interpreter; all when left out")
    ] = None,
) -> None:
    """Early feedback: unproven interpreters speak, tagged "speculative · unproven for you"."""
    from mufuse.companion.store import Store
    from mufuse.observe.interpreters import REGISTRY
    from mufuse.observe.ledger import set_early

    if state not in ("on", "off") or (id_ is not None and id_ not in REGISTRY):
        console.print(f"Use on or off, and --id one of: {', '.join(REGISTRY)}", markup=False)
        raise typer.Exit(EXIT_BAD_ARGS)
    store = Store()
    try:
        for name in [id_] if id_ else list(REGISTRY):
            set_early(store, name, state == "on")
            console.print(f"{name}: early feedback {state}", markup=False, highlight=False)
    finally:
        store.close()


# mufuse quality ------------------------------------------------------------------------------

quality_app = typer.Typer(no_args_is_help=True, help="Signal quality: labelled session and score.")
app.add_typer(quality_app, name="quality")


def _label(
    attempt: _Attempt,
    factory: Callable[[], HeadbandSource],
    read_key: Callable[[], str | None],
    out: Path,
    *,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
    check: Preflight | None = None,
    on_start: Callable[[], None] | None = None,
) -> tuple[int, ScoreReport | None, Path | None]:
    """Record the labelled session, then score it and check the replay. Returns the exit code,
    the report (None when it was stopped early) and the session folder."""
    folder: list[Path] = []

    def writer(src: HeadbandSource) -> SessionWriter:
        w = SessionWriter.create(
            out, src.device, src.streams, notes="labelled session", clock=clock
        )
        folder.append(w.session_dir)
        return w

    stats = LiveStats(clock)
    _run(
        attempt,
        factory,
        RUN_S,
        writer,
        clock=clock,
        sleep=sleep,
        read_key=read_key,
        stats=stats,
        guide=labelled_guide(),
        preflight=check,
        on_start=on_start,
    )
    session = load_session(folder[0])
    cues = cues_from_markers(session.markers)
    if not any(c.kind == "end" for c in cues):
        console.print("Stopped before the end: the session is saved, but not scored.")
        return EXIT_INTERRUPTED, None, folder[0]
    quality = judge(session)
    replay = stats.answers == quality.answers and stats.blinks == quality.blinks
    report = score(quality, cues, replay=replay)
    for line in report_lines(report):
        console.print(line, markup=False, highlight=False)
    return 0, report, folder[0]


@quality_app.command("label")
def quality_label(
    source: Annotated[
        SourceKind, typer.Option(help="athena = headband, sim = a simulated wearer who follows")
    ] = SourceKind.athena,
    device: DeviceOpt = None,
    out: Annotated[Path, typer.Option(help="Recordings folder")] = Path("recordings"),
    check: Annotated[
        bool, typer.Option(help="Check the fit first; after 60 s you may start anyway")
    ] = True,
) -> None:
    """Check the fit, record the guided labelled session (about 9.5 minutes), then score it."""
    if source is SourceKind.play:
        console.print("[red]A labelled session is recorded live: use --source athena or sim[/red]")
        raise typer.Exit(EXIT_BAD_ARGS)
    attempt = _Attempt.begin("quality label", source, DEFAULT_PRESET)
    if source is SourceKind.sim:
        from mufuse.acquisition.simulated import Rehearsal

        rehearsal = Rehearsal(rehearsal_wearer())
        factory: Callable[[], HeadbandSource] = rehearsal.source
        read_key = lambda: rehearsal.read_key() or _read_key()  # noqa: E731
        # The scripted wearer follows the cues, so the script waits for the check as well.
        on_start: Callable[[], None] | None = lambda: rehearsal.delay_script(rehearsal.now())  # noqa: E731
    else:
        factory, read_key = _source_factory(source, device, DEFAULT_PRESET, None)
        on_start = None
    preflight = Preflight() if check else None
    with _KEYS:
        code, _, _ = _label(attempt, factory, read_key, out, check=preflight, on_start=on_start)
    raise typer.Exit(code)


@quality_app.command("score")
def quality_score(
    path: Annotated[Path | None, typer.Argument(help="A labelled session folder")] = None,
    public: Annotated[
        Path | None, typer.Option(help="Score the public Muse 2 set in this folder instead")
    ] = None,
) -> None:
    """Score a recorded labelled session against its cues, or the public Muse 2 set."""
    if public is not None:
        from mufuse.quality.public_set import NotTheSetError, public_lines, score_public

        try:
            result = score_public(public)
        except NotTheSetError as exc:
            console.print(f"Not the public set: {exc}", markup=False, highlight=False)
            raise typer.Exit(EXIT_BAD_ARGS) from exc
        for line in public_lines(result):
            console.print(line, markup=False, highlight=False)
        raise typer.Exit(0 if result.passed else 1)
    if path is None:
        console.print("Give a session folder, or --public DIR.")
        raise typer.Exit(EXIT_BAD_ARGS)
    try:
        session = load_session(path)
    except (OSError, ValueError, KeyError) as exc:
        console.print(f"[red]Cannot read session: {exc}[/red]")
        raise typer.Exit(EXIT_UNREADABLE) from exc
    cues = cues_from_markers(session.markers)
    if not cues:
        console.print("This session holds no cue markers: it is not a labelled session.")
        raise typer.Exit(EXIT_BAD_ARGS)
    report = score(judge(session), cues)
    for line in report_lines(report):
        console.print(line, markup=False, highlight=False)
    raise typer.Exit(0 if report.passed else 1)


# mufuse fnirs (004, experimental) ------------------------------------------------------------

fnirs_app = typer.Typer(
    no_args_is_help=True, help="fNIRS (EXPERIMENTAL): relative hemoglobin changes, validation."
)
app.add_typer(fnirs_app, name="fnirs")


def _load_or_exit(path: Path) -> LoadedSession:
    try:
        return load_session(path)
    except (OSError, ValueError, KeyError) as exc:
        console.print(f"[red]Cannot read session: {exc}[/red]")
        raise typer.Exit(EXIT_UNREADABLE) from exc


@fnirs_app.command("show")
def fnirs_show(
    path: Annotated[Path, typer.Argument(help="A recorded session folder")],
    csv_out: Annotated[
        Path | None, typer.Option("--csv", help="Also write ΔHbO/ΔHbR per sample to this file")
    ] = None,
    short_channel: Annotated[
        bool, typer.Option(help="Regress the inner detectors out (unverified geometry)")
    ] = False,
) -> None:
    """Relative ΔHbO and ΔHbR per detector of a recorded session. EXPERIMENTAL."""
    from mufuse.fnirs.pipeline import NotAvailableError, analyze
    from mufuse.fnirs.report import hemo_lines, write_csv

    session = _load_or_exit(path)
    try:
        hemo = analyze(session, short_channel=short_channel)
    except NotAvailableError as exc:
        console.print(f"fNIRS: not available ({exc})", markup=False, highlight=False)
        raise typer.Exit(EXIT_BAD_ARGS) from exc
    for line in hemo_lines(hemo):
        console.print(line, markup=False, highlight=False)
    if csv_out is not None:
        write_csv(hemo, csv_out)
        console.print(f"Wrote {hemo.t.size} rows: {csv_out}", markup=False, highlight=False)


def _fnirs_protocol(
    attempt: _Attempt,
    factory: Callable[[], HeadbandSource],
    read_key: Callable[[], str | None],
    out: Path,
    *,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
    check: Preflight | None = None,
    on_start: Callable[[], None] | None = None,
) -> tuple[int, FnirsScore | None, Path | None]:
    """Record the guided protocol, then score it. Returns the exit code, the score (None when it
    was stopped early) and the session folder."""
    from mufuse.fnirs.pipeline import NotAvailableError, analyze
    from mufuse.fnirs.protocol import RUN_S as FNIRS_RUN_S
    from mufuse.fnirs.protocol import cues_from_markers as fnirs_cues
    from mufuse.fnirs.protocol import protocol_guide, score_lines
    from mufuse.fnirs.protocol import score as fnirs_score

    folder: list[Path] = []

    def writer(src: HeadbandSource) -> SessionWriter:
        w = SessionWriter.create(out, src.device, src.streams, notes="fnirs protocol", clock=clock)
        folder.append(w.session_dir)
        return w

    stats = LiveStats(clock)
    _run(
        attempt,
        factory,
        FNIRS_RUN_S,
        writer,
        clock=clock,
        sleep=sleep,
        read_key=read_key,
        stats=stats,
        guide=protocol_guide(),
        preflight=check,
        on_start=on_start,
    )
    if not folder:
        return EXIT_INTERRUPTED, None, None
    session = load_session(folder[0])
    cues = fnirs_cues(session.markers)
    if not any(c.kind == "end" for c in cues):
        console.print("Stopped before the end: the session is saved, but not scored.")
        return EXIT_INTERRUPTED, None, folder[0]
    quality = SessionQuality.of(stats.answers, stats.blinks)  # judged live, the same as replayed
    try:
        result = fnirs_score(analyze(session, quality), cues)
    except NotAvailableError as exc:
        console.print(f"fNIRS: not available ({exc})", markup=False, highlight=False)
        return EXIT_BAD_ARGS, None, folder[0]
    for line in score_lines(result):
        console.print(line, markup=False, highlight=False)
    return 0, result, folder[0]


@fnirs_app.command("protocol")
def fnirs_protocol(
    source: Annotated[
        SourceKind, typer.Option(help="athena = headband, sim = a simulated wearer who follows")
    ] = SourceKind.athena,
    device: DeviceOpt = None,
    out: Annotated[Path, typer.Option(help="Recordings folder")] = Path("recordings"),
    check: Annotated[
        bool, typer.Option(help="Check the fit first; after 60 s you may start anyway")
    ] = True,
) -> None:
    """Check the fit, record the guided fNIRS protocol (about 12 minutes), then score it."""
    if source is SourceKind.play:
        console.print("[red]The protocol is recorded live: use --source athena or sim[/red]")
        raise typer.Exit(EXIT_BAD_ARGS)
    from mufuse.fnirs.protocol import rehearsal_wearer as fnirs_wearer

    attempt = _Attempt.begin("fnirs protocol", source, DEFAULT_PRESET)
    if source is SourceKind.sim:
        from mufuse.acquisition.simulated import Rehearsal

        rehearsal = Rehearsal(fnirs_wearer())
        factory: Callable[[], HeadbandSource] = rehearsal.source
        read_key = lambda: rehearsal.read_key() or _read_key()  # noqa: E731
        # The scripted wearer follows the cues, so the script waits for the check as well.
        on_start: Callable[[], None] | None = lambda: rehearsal.delay_script(rehearsal.now())  # noqa: E731
    else:
        factory, read_key = _source_factory(source, device, DEFAULT_PRESET, None)
        on_start = None
    preflight = Preflight() if check else None
    with _KEYS:
        code, _, _ = _fnirs_protocol(
            attempt, factory, read_key, out, check=preflight, on_start=on_start
        )
    raise typer.Exit(code)


@fnirs_app.command("score")
def fnirs_score_cmd(
    path: Annotated[Path, typer.Argument(help="A recorded protocol session folder")],
) -> None:
    """Score a recorded fNIRS protocol session again. EXPERIMENTAL."""
    from mufuse.fnirs.pipeline import NotAvailableError, analyze
    from mufuse.fnirs.protocol import cues_from_markers as fnirs_cues
    from mufuse.fnirs.protocol import score as fnirs_score
    from mufuse.fnirs.protocol import score_lines

    session = _load_or_exit(path)
    cues = fnirs_cues(session.markers)
    if not cues:
        console.print("This session holds no f: cue markers: it is not a protocol session.")
        raise typer.Exit(EXIT_BAD_ARGS)
    try:
        result = fnirs_score(analyze(session), cues)
    except NotAvailableError as exc:
        console.print(f"fNIRS: not available ({exc})", markup=False, highlight=False)
        raise typer.Exit(EXIT_BAD_ARGS) from exc
    for line in score_lines(result):
        console.print(line, markup=False, highlight=False)
    raise typer.Exit(0 if result.passed else 1)


# mufuse breathe / mufuse exercise (009) --------------------------------------------------------


def _breathe(
    attempt: _Attempt,
    factory: Callable[[], HeadbandSource],
    read_key: Callable[[], str | None],
    out: Path,
    guide: Guide,
    rate: float,
    *,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
    check: Preflight | None = None,
    on_start: Callable[[], None] | None = None,
) -> tuple[int, BreatheReport | None, Path | None]:
    """Record the breathing session, then measure it. Returns the exit code, the report (None
    when it was stopped early) and the session folder."""
    folder: list[Path] = []

    def writer(src: HeadbandSource) -> SessionWriter:
        w = SessionWriter.create(out, src.device, src.streams, notes="breathe", clock=clock)
        folder.append(w.session_dir)
        return w

    _run(
        attempt,
        factory,
        guide.duration,
        writer,
        clock=clock,
        sleep=sleep,
        read_key=read_key,
        guide=guide,
        preflight=check,
        on_start=on_start,
    )
    report = measure(load_session(folder[0]), rate)
    if report is None:
        console.print("Stopped before the end: the session is saved, but not measured.")
        return EXIT_INTERRUPTED, None, folder[0]
    for line in breathe_lines(report):
        console.print(line, markup=False, highlight=False)
    return 0, report, folder[0]


@app.command()
def breathe(
    source: Annotated[
        SourceKind, typer.Option(help="athena = headband, sim = a simulated wearer who follows")
    ] = SourceKind.athena,
    device: DeviceOpt = None,
    rate: Annotated[float, typer.Option(help="Breaths a minute while pacing")] = DEFAULT_RATE,
    minutes: Annotated[float, typer.Option(help="Minutes of paced breathing")] = DEFAULT_MINUTES,
    out: Annotated[Path, typer.Option(help="Recordings folder")] = Path("recordings"),
    check: Annotated[
        bool, typer.Option(help="Check the fit first; after 60 s you may start anyway")
    ] = True,
) -> None:
    """Paced breathing: 2 min quiet, N min at the pace, 2 min quiet, then what the pulse did."""
    try:
        guide = breathe_guide(rate, minutes)
    except ValueError as exc:
        console.print(str(exc), markup=False, highlight=False)
        raise typer.Exit(EXIT_BAD_ARGS) from exc
    if source is SourceKind.play:
        console.print("[red]A breathing session is recorded live: use --source athena or sim[/red]")
        raise typer.Exit(EXIT_BAD_ARGS)
    attempt = _Attempt.begin("breathe", source, DEFAULT_PRESET)
    on_start: Callable[[], None] | None = None
    if source is SourceKind.sim:
        from mufuse.acquisition.simulated import Rehearsal

        rehearsal = Rehearsal(breathe_wearer(rate, minutes))
        factory: Callable[[], HeadbandSource] = rehearsal.source
        read_key = lambda: rehearsal.read_key() or _read_key()  # noqa: E731
        on_start = lambda: rehearsal.delay_script(rehearsal.now())  # noqa: E731
    else:
        factory, read_key = _source_factory(source, device, DEFAULT_PRESET, None)
    with _KEYS:
        code, _, _ = _breathe(
            attempt,
            factory,
            read_key,
            out,
            guide,
            rate,
            check=Preflight() if check else None,
            on_start=on_start,
        )
    raise typer.Exit(code)


exercise_app = typer.Typer(no_args_is_help=True, help="Short guided exercises (009).")
app.add_typer(exercise_app, name="exercise")


def _play(
    guide: Guide,
    *,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
    read_key: Callable[[], str | None] = _read_key,
) -> int:
    """Show a guide without a headband until it ends or `q` is pressed. Returns the exit code."""
    started, shown = clock(), ""
    with _stop_on_ctrl_c() as stop:
        while not stop.is_set():
            elapsed = clock() - started
            if elapsed >= guide.duration:
                return 0
            text, _ = guide.current(elapsed)
            if text != shown:
                shown = text
                line = f"{_mmss(elapsed)}  {text}"
                console.print(line, markup=False, highlight=False, soft_wrap=True)
            if read_key() == "q":
                console.print("Stopped.", markup=False, highlight=False)
                return 0
            sleep(0.2)
    return EXIT_INTERRUPTED


def _exercise(name: str, source: SourceKind | None, device: str | None, out: Path) -> None:
    guide = load_exercise(name).guide()
    if source is None:
        with _KEYS:
            raise typer.Exit(_play(guide))
    if source is SourceKind.play:
        console.print("[red]Use --source athena or sim, or no --source at all[/red]")
        raise typer.Exit(EXIT_BAD_ARGS)
    factory, read_key = _source_factory(source, device, DEFAULT_PRESET, None)

    def writer(src: HeadbandSource) -> SessionWriter:
        return SessionWriter.create(out, src.device, src.streams, notes=f"exercise {name}")

    with _KEYS:
        _run(
            _Attempt.begin(f"exercise {name}", source, DEFAULT_PRESET),
            factory,
            guide.duration,
            writer,
            read_key=read_key,
            guide=guide,
        )


ExerciseSourceOpt = Annotated[
    SourceKind | None,
    typer.Option(help="Also record with the headband (athena) or the simulator (sim)"),
]


@exercise_app.command("defusion")
def exercise_defusion(
    source: ExerciseSourceOpt = None,
    device: DeviceOpt = None,
    out: Annotated[Path, typer.Option(help="Recordings folder")] = Path("recordings"),
) -> None:
    """Stepping back from a thought: about four minutes of short steps on screen."""
    _exercise("defusion", source, device, out)


@exercise_app.command("urge")
def exercise_urge(
    source: ExerciseSourceOpt = None,
    device: DeviceOpt = None,
    out: Annotated[Path, typer.Option(help="Recordings folder")] = Path("recordings"),
) -> None:
    """Watching an urge rise and fall: about four minutes of short steps on screen."""
    _exercise("urge", source, device, out)
