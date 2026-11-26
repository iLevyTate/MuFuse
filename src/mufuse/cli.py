"""MuFuse command-line interface: devices / stream / record / inspect."""

from __future__ import annotations

import contextlib
import io
import os
import signal
import sys
import threading
import time
from collections import deque
from collections.abc import Callable, Generator
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from types import FrameType
from typing import Annotated

import numpy as np
import typer
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from mufuse.acquisition.athena import ATHENA_STREAMS, DEFAULT_PRESET, validate_preset
from mufuse.acquisition.signal_check import classify_channel
from mufuse.acquisition.source import HeadbandSource
from mufuse.acquisition.supervisor import State, StreamSupervisor
from mufuse.acquisition.types import Chunk, SourceError, StreamKind
from mufuse.banner import CLI_ORANGE, print_banner
from mufuse.config import load_config, save_config
from mufuse.guide import Guide, guide_from_env
from mufuse.recording.format import Marker
from mufuse.recording.reader import load_session
from mufuse.recording.writer import SessionWriter
from mufuse.runlog import ConnectRun, TimeToSignal, append_run

app = typer.Typer(
    no_args_is_help=True, help="MuFuse: Punk EEG. Muse S Athena acquisition and recording."
)
console = Console()

EXIT_BAD_ARGS, EXIT_NONE_FOUND, EXIT_CONNECT, EXIT_WRITE, EXIT_UNREADABLE = 2, 3, 4, 5, 6
EXIT_INTERRUPTED = 130  # Ctrl+C before anything was shown or recorded
WINDOW_S = 2.0


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


class LiveStats:
    """Rolling window of recent chunks for the live view."""

    def __init__(self) -> None:
        self._recent: dict[StreamKind, deque[Chunk]] = {k: deque() for k in StreamKind}

    def add(self, chunks: list[Chunk], now: float) -> None:
        for chunk in chunks:
            self._recent[chunk.kind].append(chunk)
        for q in self._recent.values():
            while q and q[0].timestamps[-1] < now - WINDOW_S:
                q.popleft()

    def window(self, kind: StreamKind) -> np.ndarray:
        q = self._recent[kind]
        if not q:
            return np.empty((0, len(ATHENA_STREAMS[kind].channel_names)))
        return np.vstack([c.data for c in q])

    def rate(self, kind: StreamKind) -> float:
        return sum(c.n_samples for c in self._recent[kind]) / WINDOW_S


def _render(
    sup: StreamSupervisor, stats: LiveStats, recording: str | None, markers: int = 0
) -> Table:
    table = Table(
        title=f"MuFuse — {sup.state.value}" + (f" — REC {recording}" if recording else "")
    )
    table.add_column("stream")
    table.add_column("rate (Hz)", justify="right")
    table.add_column("detail")
    eeg = stats.window(StreamKind.EEG)
    names = ATHENA_STREAMS[StreamKind.EEG].channel_names[:4]
    status = (
        "  ".join(
            f"{n}:{classify_channel(eeg[:, i] - eeg[:, i].mean())}" for i, n in enumerate(names)
        )
        if eeg.shape[0]
        else "waiting…"
    )
    table.add_row("EEG", f"{stats.rate(StreamKind.EEG):.0f}/256", status)
    table.add_row("Motion", f"{stats.rate(StreamKind.MOTION):.0f}/52", "")
    optics = stats.window(StreamKind.OPTICS)
    battery = f"battery {optics[-1, -1]:.0f}%" if optics.shape[0] else ""
    table.add_row("Optics", f"{stats.rate(StreamKind.OPTICS):.0f}/64", battery)
    if sup.state is State.RECONNECTING:
        table.add_row("Link", "", sup.last_error or "reconnecting…")
    if recording:
        table.add_row("Markers", "", f"{markers} saved")  # so a key press is seen to land
        table.caption = "space = moment marker · 1-9 = start/end block · q = stop"
    return table


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


_STEP_STYLE = {"done": ("✓", "dim"), "now": ("▶", f"bold {CLI_ORANGE}"), "next": ("·", "bold")}


def _guide_panel(guide: Guide, elapsed: float) -> Panel:
    """What we're doing, the instruction right now with its countdown, and the whole timeline."""
    steps = Table.grid(padding=(0, 1))
    for at, text, state in guide.timeline(elapsed):
        mark, style = _STEP_STYLE.get(state, (" ", ""))
        steps.add_row(mark, f"{int(at) // 60}:{int(at) % 60:02d}", text, style=style)
    progress = ProgressBar(
        total=guide.duration,
        completed=min(elapsed, guide.duration),
        width=40,
        complete_style=CLI_ORANGE,
    )
    now = Text(f" {guide.prompt(elapsed)} ", style=f"bold black on {CLI_ORANGE}")
    return Panel(
        Group(now, Text(""), steps, Text(""), progress),
        title=guide.title or "Guided session",
        subtitle=guide.clock(elapsed),
        title_align="left",
        subtitle_align="right",
        border_style=CLI_ORANGE,
    )


def _read_key() -> str | None:
    if sys.platform == "win32":
        import msvcrt

        if msvcrt.kbhit():
            return msvcrt.getwch()
    return None


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
) -> None:
    sup = StreamSupervisor(factory, clock=clock)
    with _stop_on_ctrl_c() as stop:
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
        try:
            _show_and_record(sup, timer, duration, writer_factory, stop, clock, sleep, read_key)
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
) -> None:
    """The live loop. Whatever ends it, the session is finalized before this returns."""
    assert sup.source is not None
    writer = writer_factory(sup.source) if writer_factory else None
    try:
        if writer is not None:
            sup.on_gap_closed = writer.add_gap
            sup.on_reconnect_step = writer.add_reconnect_step
        recording = writer.session_dir.name if writer else None
        guide = guide_from_env()
        stats, open_blocks, markers = LiveStats(), set[str](), 0
        latest: list[RenderableType] = [_render(sup, stats, recording)]
        while read_key() is not None:  # keys typed while it was connecting are not for this run
            pass
        started = clock()

        def view() -> RenderableType:
            # Runs on Live's refresh thread, so a guide's countdown keeps moving even while a
            # reconnect attempt blocks the loop below.
            if guide is None:
                return latest[0]
            return Group(latest[0], _guide_panel(guide, clock() - started))

        with Live(console=console, refresh_per_second=4, get_renderable=view) as live:
            # The time limit is checked before every poll, so no reconnect attempt begins
            # after it has passed.
            while not stop.is_set() and (duration is None or clock() - started < duration):
                chunks = sup.poll()
                now = clock()
                stats.add(chunks, now)
                if (seconds := timer.observe(chunks, now)) is not None:
                    live.console.print(f"first EEG after {seconds:.1f} s")
                if writer is not None:
                    writer.write(chunks)
                    for label, offset in guide.due(now - started) if guide else []:
                        t = started + offset
                        writer.add_marker(Marker(t=t, kind="system", label=label, source="system"))
                key = read_key()
                if key == "q":
                    break
                if writer is not None and (marker := _key_marker(key, open_blocks, now)):
                    writer.add_marker(marker)
                    markers += 1
                latest[0] = _render(sup, stats, recording, markers)
                sleep(0.05)
    finally:
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


def _release(attempt: _Attempt, sup: StreamSupervisor) -> None:
    """Let go of the headband. Nothing depends on how this ends."""
    if attempt.source is SourceKind.athena:
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
