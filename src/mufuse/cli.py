"""MuFuse command-line interface: devices / stream / record / inspect."""

from __future__ import annotations

import sys
import time
from collections import deque
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import numpy as np
import typer
from rich.console import Console
from rich.live import Live
from rich.table import Table

from mufuse.acquisition.athena import ATHENA_STREAMS, DEFAULT_PRESET, validate_preset
from mufuse.acquisition.signal_check import classify_channel
from mufuse.acquisition.source import HeadbandSource
from mufuse.acquisition.supervisor import State, StreamSupervisor
from mufuse.acquisition.types import Chunk, SourceError, StreamKind
from mufuse.config import load_config, save_config
from mufuse.recording.format import Marker
from mufuse.recording.reader import load_session
from mufuse.recording.writer import SessionWriter

app = typer.Typer(no_args_is_help=True, help="MuFuse: Muse S Athena acquisition and recording.")
console = Console()

EXIT_BAD_ARGS, EXIT_NONE_FOUND, EXIT_CONNECT, EXIT_WRITE, EXIT_UNREADABLE = 2, 3, 4, 5, 6
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


def _source_factory(
    source: SourceKind, device: str | None, preset: str, play: Path | None
) -> Callable[[], HeadbandSource]:
    try:
        validate_preset(preset)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(EXIT_BAD_ARGS) from exc
    if source is SourceKind.sim:
        from mufuse.acquisition.simulated import SimulatedAthena

        return lambda: SimulatedAthena(preset=preset)
    if source is SourceKind.play:
        if play is None:
            console.print("[red]--play PATH is required with --source play[/red]")
            raise typer.Exit(EXIT_BAD_ARGS)
        from mufuse.acquisition.playback import PlaybackSource

        return lambda: PlaybackSource(play)
    from mufuse.acquisition.brainflow_athena import BrainFlowAthena

    name = device or _remembered_or_scanned_device()
    return lambda: BrainFlowAthena(device_name=name, preset=preset)


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


def _render(sup: StreamSupervisor, stats: LiveStats, recording: str | None) -> Table:
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
    if recording:
        table.caption = "space = moment marker · 1-9 = start/end block · q = stop"
    return table


def _read_key() -> str | None:
    if sys.platform == "win32":
        import msvcrt

        if msvcrt.kbhit():
            return msvcrt.getwch()
    return None


def _run(
    factory: Callable[[], HeadbandSource],
    duration: float | None,
    writer_factory: Callable[[HeadbandSource], SessionWriter] | None = None,
) -> None:
    sup = StreamSupervisor(factory)
    try:
        sup.start()
    except SourceError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(EXIT_CONNECT) from exc
    assert sup.source is not None
    writer = writer_factory(sup.source) if writer_factory else None
    if writer is not None:
        sup.on_gap_closed = writer.add_gap
    stats, open_blocks, started = LiveStats(), set[str](), time.time()
    try:
        with Live(_render(sup, stats, None), console=console, refresh_per_second=4) as live:
            while duration is None or time.time() - started < duration:
                chunks = sup.poll()
                now = time.time()
                stats.add(chunks, now)
                if writer is not None:
                    writer.write(chunks)
                    if _handle_key(_read_key(), writer, open_blocks, now):
                        break
                elif _read_key() == "q":
                    break
                live.update(_render(sup, stats, writer.session_dir.name if writer else None))
                time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        console.print(f"[red]Write error: {exc}[/red]")
        raise typer.Exit(EXIT_WRITE) from exc
    finally:
        sup.stop()
        if writer is not None:
            writer.finalize()
            console.print(f"Saved session: {writer.session_dir}")
    if sup.state is State.RECONNECTING:
        console.print("[yellow]Stopped while reconnecting; the open gap was not closed.[/yellow]")


def _handle_key(key: str | None, writer: SessionWriter, open_blocks: set[str], now: float) -> bool:
    """Returns True when the user asked to stop."""
    if key is None:
        return False
    if key == "q":
        return True
    if key == " ":
        writer.add_marker(Marker(t=now, kind="moment", label="moment", source="keyboard"))
    elif key.isdigit() and key != "0":
        label = f"block {key}"
        kind = "block_end" if label in open_blocks else "block_start"
        open_blocks.symmetric_difference_update({label})
        writer.add_marker(Marker(t=now, kind=kind, label=label, source="keyboard"))
    return False


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
    _run(_source_factory(source, device, preset, play), duration)


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
    factory = _source_factory(source, device, preset, play)
    _run(
        factory,
        duration,
        lambda src: SessionWriter.create(out, src.device, src.streams, notes=notes),
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
        f"preset={m['device']['preset']}  notes={m['notes']!r}"
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
    for g in session.gaps:
        dur = f"{g.end - g.start:.2f} s" if g.end is not None else "open"
        console.print(f"    gap {g.reason} {dur}")
