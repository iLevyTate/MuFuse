"""The live view of `mufuse stream` and `mufuse record` (issue #13).

Laid out so the first question, "is it on right?", is answered first:

1. a two-line header: recording, elapsed time, link state, battery; session id and device below;
2. the sensors panel: a readiness line (READY / FITTING and which sensor to fix first), a plain
   position map of every sensor (forehead EEG, the four fNIRS detectors around their light source,
   the reference, the ear sensors), and beside it one fixed-width row per sensor with its grade,
   a 2 s trace and a number; then one tip for the worst sensor;
3. the quality block: the coverage of the newest judged second and the sensors that are out,
   then the signal: blinks counted so far, muscle activity and head movement in that second;
4. one streams line: rate and share received per stream, gaps, markers;
5. the guide of a guided session, and the keys.

Contact, coverage and the signal marks come from the quality engine (`mufuse.quality.engine`),
one answer per judged second, so nothing on them changes more often than once a second.

Every column has a fixed width so a changing value never moves the rest. From 78 columns the
map sits beside the list; below that they stack instead of wrapping.

It has to read in every terminal. Grades show as a shape and a word, not only a colour. The
glyphs come from the WGL4 set that Consolas, Cascadia and Lucida Console all carry, except the
trace bars; when the output cannot encode them (a cp1252 console, a redirected file), when Rich
draws through the legacy Windows console API, or when MUFUSE_ASCII=1, plain ASCII is used
instead. A view that is not a terminal (piped, redirected) gets one status line at a time from
`status_line` instead of a redrawn panel (cli.py).

The contact map is a plain position map, never a horseshoe: Muse's brand guidelines forbid
replicating their indicator (docs/BRAND.md). Colours grade the signal only, never the person.
"""

from __future__ import annotations

import io
import math
import os
import time
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace

import numpy as np
from rich import box
from rich.console import Console, ConsoleOptions, Group, RenderableType, RenderResult
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from mufuse.acquisition.athena import ATHENA_STREAMS, preset_warning
from mufuse.acquisition.contact import SENSORS, Grade, Reading, SensorView, Why, tip
from mufuse.acquisition.optics import (
    DETECTORS,
    PULSE_WINDOW_S,
    DetectorGrade,
    detector_grades,
    too_much_light,
)
from mufuse.acquisition.supervisor import State, StreamSupervisor
from mufuse.acquisition.types import Chunk, DeviceInfo, FloatArray, StreamKind
from mufuse.banner import CLI_ORANGE
from mufuse.guide import Guide
from mufuse.quality.answer import Blink, ContactState, Coverage, Movement, QualityAnswer
from mufuse.quality.engine import QualityEngine

# docs/BRAND.md: scope-green, fair-amber, clip-red; the CLI orange; muted greys for labels.
GREEN, YELLOW, RED = "#22C55E", "#EAB308", "#EF4444"
DIM, BORDER, INK = "#8B949E", "#6B7280", "#C9D1D9"

WINDOW_S = 2.0  # rates and traces are taken over this long
CONTACT_S = 1.0  # contact is graded on this long
MAP_W = 28  # the position map
WIDE = 78  # narrower than this, the map stacks above the list
TRACE_N = 10  # bars in a 2 s trace
TRACE_LO_UV, TRACE_HI_UV = 5.0, 500.0  # a bar's floor and ceiling, log scale
GOOD_PCT, FAIR_PCT = 95.0, 80.0  # share received: green from GOOD_PCT, yellow from FAIR_PCT
SIXTEEN = ("p1041", "p1042")  # presets with the 16-row optics layout

_STREAMS = ((StreamKind.EEG, "EEG"), (StreamKind.MOTION, "Motion"), (StreamKind.OPTICS, "Optics"))


@dataclass(frozen=True)
class Glyphs:
    good: str
    wait: str
    none: str
    idle: str
    led_good: str
    led_wait: str
    source: str
    bars: str
    done: str
    now: str
    next: str
    tip: str
    rec: str


UNICODE = Glyphs(
    good="●", wait="○", none="×", idle="·", led_good="■", led_wait="□", source="♦",  # noqa: RUF001
    bars="▁▂▃▄▅▆▇█", done="√", now="►", next="·", tip="›", rec="●",  # noqa: RUF001
)  # fmt: skip
ASCII = Glyphs(
    good="O", wait="o", none="x", idle=".", led_good="#", led_wait="+", source="*",
    bars="_.:-=+*#", done="v", now=">", next="-", tip=">", rec="*",
)  # fmt: skip


def glyphs_for(options: ConsoleOptions) -> Glyphs:
    """ASCII when asked (MUFUSE_ASCII=1), when the output can't encode Unicode, or on legacy
    Windows consoles; the WGL4 set otherwise."""
    if os.environ.get("MUFUSE_ASCII", "") == "1" or options.ascii_only or options.legacy_windows:
        return ASCII
    return UNICODE


# Grades of EEG sensors (contact.py) and fNIRS detectors (optics.py): colour, word, glyph kind.
_EEG: dict[str, tuple[str, str, str]] = {
    "good": (GREEN, "good", "good"),
    "settling": (YELLOW, "settling", "wait"),
    "noisy": (YELLOW, "noisy", "wait"),
    "none": (RED, "no contact", "none"),
    "waiting": (DIM, "waiting", "idle"),
}
_LED: dict[str, tuple[str, str, str]] = {
    "pulse": (GREEN, "pulse seen", "led_good"),
    "finding": (YELLOW, "finding pulse", "led_wait"),
    "light": (RED, "light leaking", "none"),
    "none": (RED, "no reading", "none"),
}


def _mark(g: Glyphs, kind: str) -> str:
    return str(getattr(g, kind))


class LiveStats:
    """Rolling window of recent chunks, and what the view keeps between refreshes."""

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        # `clock` is kept for callers; contact is judged on sample timestamps, not on a clock.
        self._recent: dict[StreamKind, deque[Chunk]] = {k: deque() for k in StreamKind}
        self._since: float | None = None
        self._now = 0.0
        self.battery: float | None = None  # the last level the headband reported
        self._engine = QualityEngine()
        self._answers: list[QualityAnswer] = []
        self._blinks: list[Blink] = []

    @property
    def answers(self) -> tuple[QualityAnswer, ...]:
        """Every answer the engine gave so far, in time order."""
        return tuple(self._answers)

    @property
    def blinks(self) -> tuple[Blink, ...]:
        """Every blink the engine found so far, in time order."""
        return tuple(self._blinks)

    def add(self, chunks: list[Chunk], now: float) -> None:
        self._since = now if self._since is None else self._since
        self._now = now
        judged = self._engine.feed(chunks)
        self._answers += judged.answers
        self._blinks += judged.blinks
        for chunk in chunks:
            self._recent[chunk.kind].append(chunk)
            if chunk.kind is StreamKind.OPTICS and chunk.n_samples:
                reported = chunk.data[chunk.data[:, -1] > 0, -1]
                if reported.size:
                    self.battery = float(reported[-1])
        for kind, q in self._recent.items():
            keep = PULSE_WINDOW_S if kind is StreamKind.OPTICS else WINDOW_S
            while q and q[0].timestamps[-1] < now - keep:
                q.popleft()

    def window(self, kind: StreamKind) -> FloatArray:
        q = self._recent[kind]
        if not q:
            return np.empty((0, len(ATHENA_STREAMS[kind].channel_names)))
        return np.vstack([c.data for c in q])

    def last(self, kind: StreamKind, seconds: float) -> FloatArray:
        """The samples of the last `seconds` before the newest one."""
        q = self._recent[kind]
        if not q:
            return self.window(kind)
        ts = np.concatenate([c.timestamps for c in q])
        return self.window(kind)[ts > ts[-1] - seconds]

    def rate(self, kind: StreamKind) -> float:
        span = WINDOW_S if self._since is None else min(WINDOW_S, self._now - self._since)
        if span <= 0:
            return 0.0
        q = self._recent[kind]
        return sum(int((c.timestamps > self._now - WINDOW_S).sum()) for c in q) / span

    def _newest(self) -> QualityAnswer | None:
        """The newest judged second, or None before the first one and after a gap."""
        newest = self._answers[-1] if self._answers else None
        return None if newest is None or newest.no_data else newest

    def contact(self) -> tuple[SensorView, ...]:
        newest = self._newest()
        if newest is None:
            return tuple(SensorView(name, "waiting", None) for name in SENSORS)
        return tuple(self._view(c) for c in newest.contact)

    def coverage(self) -> Coverage | None:
        newest = self._newest()
        return None if newest is None else newest.coverage

    def signal(self) -> SignalMarks | None:
        """The blink count and the marks of the newest judged second."""
        newest = self._newest()
        if newest is None:
            return None
        blinks = None if newest.eye == "unavailable" else len(self._blinks)
        return SignalMarks(blinks, newest.tension == "yes", newest.movement)

    def _view(self, c: ContactState) -> SensorView:
        grade: Grade = "none" if c.state == "none" else "noisy" if c.state == "noisy" else "good"
        why: Why = "quiet" if c.reason is None else c.reason
        left = self._engine.settle_left(c.sensor) if c.state == "settling" else 0
        return SensorView(c.sensor, c.state, Reading(grade, why, c.spread_uv, c.mains_share), left)

    def traces(self) -> dict[str, tuple[float, ...]]:
        """Per EEG sensor, the spread (µV) of each of TRACE_N slices of the last 2 s."""
        eeg = self.last(StreamKind.EEG, WINDOW_S)
        if eeg.shape[0] < TRACE_N * 2:
            return {}
        out: dict[str, tuple[float, ...]] = {}
        for i, name in enumerate(SENSORS):
            parts = np.array_split(eeg[:, i] - eeg[:, i].mean(), TRACE_N)
            out[name] = tuple(float(p.std()) for p in parts)
        return out

    def detectors(self, preset: str) -> dict[str, DetectorGrade]:
        return detector_grades(
            self.last(StreamKind.OPTICS, PULSE_WINDOW_S), sixteen_channels=preset in SIXTEEN
        )

    def too_much_light(self, preset: str) -> bool:
        frames = self.last(StreamKind.OPTICS, CONTACT_S)
        return bool(frames.shape[0]) and bool(
            too_much_light(frames, sixteen_channels=preset in SIXTEEN).any()
        )


@dataclass(frozen=True)
class SignalMarks:
    """The Signal line: blinks so far (None: not available now) and the newest second's marks."""

    blinks: int | None
    tension: bool
    movement: Movement


@dataclass(frozen=True)
class StreamRow:
    name: str
    rate: float
    nominal: float
    seen: bool


@dataclass(frozen=True)
class Screen:
    """Everything the live view shows, laid out when it is drawn (so it fits the width)."""

    recording: str | None
    elapsed: float
    state: State
    link_error: str | None
    battery: float | None
    device: DeviceInfo | None
    sensors: tuple[SensorView, ...]
    streams: tuple[StreamRow, ...]
    gaps: int
    markers: int
    glare: bool
    guide: tuple[Guide, float] | None = None  # the guide and its elapsed time
    notes: tuple[str, ...] = field(default=())
    traces: Mapping[str, tuple[float, ...]] = field(default_factory=dict[str, tuple[float, ...]])
    detectors: Mapping[str, DetectorGrade] = field(default_factory=dict[str, DetectorGrade])
    coverage: Coverage | None = None  # None until the first second is judged
    signal: SignalMarks | None = None  # likewise

    def with_time(self, elapsed: float, guide: Guide | None, guide_elapsed: float) -> Screen:
        return replace(
            self, elapsed=elapsed, guide=None if guide is None else (guide, guide_elapsed)
        )

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        g = glyphs_for(options)
        width = options.max_width
        yield _header(self, g)
        for note in self.notes:
            yield Text(f" ! {note}", style=YELLOW, overflow="fold")
        if self.state is State.RECONNECTING:
            yield Text(f" link: {self.link_error or 'reconnecting…'}", style=RED, overflow="fold")
        yield _sensors_panel(self, g, width)
        yield coverage_line(self, width)
        yield signal_line(self, width)
        yield _streams_line(self, width)
        if self.guide is not None:
            yield GuideView(*self.guide, width=min(WIDE, width))
        keys = "space marker · 1-9 start/end block · q stop" if self.recording else "q stop"
        yield Text(f" {keys}", style=DIM, no_wrap=True, overflow="ellipsis")

    def status_line(self) -> str:
        """One plain ASCII line, for output that is not a terminal (piped or redirected)."""
        by = {v.name: v for v in self.sensors}
        parts = [_mmss(self.elapsed), self.state.value]
        parts += [f"{n} {_EEG[by[n].shown][1]}" for n in SENSORS if n in by]
        parts.append("coverage " + " · ".join(words for words, _ in _coverage_pieces(self)))
        parts.append("signal " + " · ".join(words for words, _ in _signal_pieces(self)))
        if self.detectors:
            pulse = sum(v == "pulse" for v in self.detectors.values())
            parts.append(f"fNIRS {pulse}/{len(self.detectors)} pulse")
        parts += [f"{r.name} {_pct(r)}" for r in self.streams]
        if self.battery:
            parts.append(f"battery {self.battery:.0f}%")
        if self.recording:
            parts.append(f"markers {self.markers}")
        if self.guide is not None:
            text, left = self.guide[0].current(self.guide[1])
            parts.append(f"NOW: {text} ({_left(left)})")
        return " | ".join(parts)


def render(
    sup: StreamSupervisor,
    stats: LiveStats,
    recording: str | None,
    markers: int = 0,
    *,
    elapsed: float = 0.0,
) -> Screen:
    """The live view of what the supervisor and the stats hold right now."""
    device = sup.source.device if sup.source is not None else None
    notes: list[str] = []
    if device is not None:
        warning = preset_warning(device.preset, device.extra.get("active_preset"))
        if warning is not None:
            notes.append(warning)
    preset = device.preset if device else ""
    return Screen(
        recording=recording,
        elapsed=elapsed,
        state=sup.state,
        link_error=sup.last_error,
        battery=stats.battery,
        device=device,
        sensors=stats.contact(),
        streams=tuple(
            StreamRow(
                label,
                stats.rate(kind),
                ATHENA_STREAMS[kind].sampling_rate,
                bool(stats.window(kind).shape[0]),
            )
            for kind, label in _STREAMS
        ),
        gaps=len(sup.gaps) + (sup.open_gap is not None),
        markers=markers,
        glare=stats.too_much_light(preset),
        notes=tuple(notes),
        traces=stats.traces(),
        detectors=stats.detectors(preset),
        coverage=stats.coverage(),
        signal=stats.signal(),
    )


# Header ----------------------------------------------------------------------------------------


def _mmss(seconds: float) -> str:
    whole = max(int(seconds), 0)
    return f"{whole // 60:02d}:{whole % 60:02d}"


def _header(s: Screen, g: Glyphs) -> Table:
    grid = Table.grid(expand=True)
    grid.add_column(no_wrap=True, overflow="ellipsis")
    grid.add_column(justify="right", no_wrap=True, overflow="ellipsis")
    badge = (
        (f" {g.rec} REC ", f"bold white on {RED}")
        if s.recording
        else (f" {g.rec} LIVE ", "bold black on #9CA3AF")
    )
    link = (s.state.value, f"bold {GREEN}" if s.state is State.STREAMING else f"bold {RED}")
    battery = (
        Text.assemble(("battery ", DIM), (f"{s.battery:.0f}%", "bold"), " ")
        if s.battery
        else Text.assemble(("battery ", DIM), ("… ", DIM))
    )
    grid.add_row(Text.assemble(badge, "  ", (_mmss(s.elapsed), "bold"), "  ", link), battery)
    device = ""
    if s.device is not None:
        firmware = f" · fw {s.device.firmware}" if s.device.firmware else ""
        device = f"{s.device.name}{firmware} · {s.device.preset} "
    grid.add_row(Text(f" {s.recording or 'not recording'}", style=DIM), Text(device, style=DIM))
    return grid


# Sensors ---------------------------------------------------------------------------------------

_RANK = {"none": 3, "noisy": 2, "settling": 1, "good": 0, "waiting": 0}


def _readiness(s: Screen) -> Text:
    views = [v for v in s.sensors if v.shown != "waiting"]
    if not views:
        line = Text.assemble((" WAITING ", "bold black on #9CA3AF"), ("  for the first EEG", INK))
    elif all(v.shown == "good" for v in s.sensors):
        line = Text.assemble(
            (" READY ", f"bold black on {GREEN}"), ("  all four EEG sensors good", INK)
        )
    else:
        good = sum(v.shown == "good" for v in s.sensors)
        worst = max(s.sensors, key=lambda v: _RANK[v.shown])
        todo = f"fix {worst.name} first" if _RANK[worst.shown] >= 2 else "hold still"
        line = Text.assemble(
            (" FITTING ", f"bold black on {YELLOW}"), (f"  {good} of 4 EEG good · {todo}", INK)
        )
    if s.detectors:
        pulse = sum(v == "pulse" for v in s.detectors.values())
        line.append(f"   fNIRS {pulse} of {len(s.detectors)} with pulse", style=DIM)
    line.no_wrap, line.overflow = True, "ellipsis"
    return line


def _ref(sensors: Sequence[SensorView]) -> str:
    """The reference has no signal of its own in BrainFlow; any touching EEG sensor proves it."""
    shown = {v.shown for v in sensors}
    if shown & {"good", "settling", "noisy"}:
        return "good"
    return "none" if shown == {"none"} else "waiting"


def _position_map(s: Screen, g: Glyphs) -> list[Text]:
    """Nose up. Forehead: AF7, the detectors LO LI around the source and RI RO, AF8. REF in the
    middle of the forehead. TP9 and TP10 behind the ears. Every line is MAP_W wide."""
    by = {v.name: v for v in s.sensors}

    def eeg(name: str) -> tuple[str, str]:
        colour, _, kind = _EEG[by[name].shown if name in by else "waiting"]
        return _mark(g, kind), f"bold {colour}"

    def led(name: str) -> tuple[str, str]:
        if name not in s.detectors:
            return g.idle, DIM
        colour, _, kind = _LED[s.detectors[name]]
        return _mark(g, kind), f"bold {colour}"

    ref_colour, _, ref_kind = _EEG[_ref(s.sensors)]
    sp = ("  ", "")
    lines = [
        Text("front".center(MAP_W), style=DIM),
        Text.assemble(
            (" AF7 ", "bold"),
            eeg("AF7"),
            sp,
            led("LO"),
            sp,
            led("LI"),
            sp,
            (g.source, f"bold {CLI_ORANGE}"),
            sp,
            led("RI"),
            sp,
            led("RO"),
            sp,
            eeg("AF8"),
            (" AF8", "bold"),
        ),
        Text("       LO LI     RI RO      ", style=DIM),
        Text.assemble(
            (" " * 10 + "REF ", DIM), (_mark(g, ref_kind), f"bold {ref_colour}"), " " * 13
        ),
        Text(""),
        Text.assemble((" TP9 ", "bold"), eeg("TP9"), " " * 16, eeg("TP10"), (" TP10", "bold")),
        Text("back".center(MAP_W), style=DIM),
    ]
    for line in lines:
        line.no_wrap = True
    return lines


def _trace(values: Sequence[float], g: Glyphs) -> str:
    if not values:
        return " " * TRACE_N
    lo, hi = math.log10(TRACE_LO_UV), math.log10(TRACE_HI_UV)
    top = len(g.bars) - 1
    out: list[str] = []
    for v in values:
        level = (math.log10(max(v, 1e-9)) - lo) / (hi - lo)
        out.append(g.bars[min(max(round(level * top), 0), top)])
    return "".join(out)


def _detail(view: SensorView) -> str:
    r = view.reading
    if r is None:
        return ""
    uv = f"{min(r.spread_uv, 999):.0f} µV"
    if view.shown == "none":
        return f"hum {r.mains_share:.0%}" if r.why == "hum" else r.why  # flat, railed, floating
    return uv


def _sensor_list(s: Screen, g: Glyphs) -> Table:
    by = {v.name: v for v in s.sensors}
    t = Table.grid(padding=(0, 1))
    t.add_column(width=1, no_wrap=True)
    t.add_column(width=5, no_wrap=True)
    t.add_column(width=13, no_wrap=True)
    t.add_column(width=TRACE_N, no_wrap=True)
    t.add_column(width=8, justify="right", no_wrap=True)
    t.add_row("", Text("EEG", style=f"bold {DIM}"), "", Text("last 2 s", style=DIM), "")
    for name in SENSORS:  # TP9, AF7, AF8, TP10: left to right as worn
        view = by.get(name)
        shown = view.shown if view else "waiting"
        colour, word, kind = _EEG[shown]
        if shown == "settling" and view is not None:
            word = f"settling {view.settle_left_s} s"
        t.add_row(
            Text(_mark(g, kind), style=f"bold {colour}"),
            Text(name, style="bold"),
            Text(word, style=colour),
            Text(_trace(s.traces.get(name, ()), g), style=colour),
            Text(_detail(view) if view else "", style=DIM),
        )
    t.add_row("", "", "", "", "")
    t.add_row("", Text("fNIRS", style=f"bold {DIM}"), Text("experimental", style=DIM), "", "")
    if not s.detectors:
        t.add_row("", "", Text("not in preset", style=DIM), "", "")
    for name in DETECTORS if s.detectors else ():
        colour, word, kind = _LED[s.detectors[name]]
        t.add_row(
            Text(_mark(g, kind), style=f"bold {colour}"),
            Text(name, style="bold"),
            Text(word, style=colour),
            "",
            "",
        )
    return t


def _sensors_panel(s: Screen, g: Glyphs, width: int) -> Panel:
    body = Table.grid(padding=(0, 2))
    if width >= WIDE:
        body.add_column(width=MAP_W, no_wrap=True)
        body.add_column(no_wrap=True)
        body.add_row(Group(*_position_map(s, g)), _sensor_list(s, g))
    else:
        body.add_column(no_wrap=True)
        body.add_row(Group(*_position_map(s, g)))
        body.add_row(_sensor_list(s, g))
    parts: list[RenderableType] = [_readiness(s), Text(""), body]
    advice = tip(s.sensors)
    if advice:
        parts += [Text(""), Text.assemble((f"{g.tip} ", f"bold {CLI_ORANGE}"), (advice, INK))]
    legend = f"{g.good} good  {g.wait} settling/noisy  {g.none} no contact"
    return Panel(
        Group(*parts),
        title=f"[bold {INK}]sensors[/]",
        title_align="left",
        subtitle=f"[{DIM}]{legend}[/]",
        subtitle_align="right",
        width=min(WIDE, width),
        border_style=BORDER,
        box=box.SQUARE,
        padding=(0, 1),
    )


# Coverage --------------------------------------------------------------------------------------

COVERAGE_WORDS = {  # contracts/cli.md: the level, as the coverage line says it
    "full": "full",
    "reduced": "reduced: forehead sensors good",
    "one_forehead": "one forehead sensor",
    "none": "none",
}
SENSOR_TEXTS = {  # contracts/cli.md: a sensor that is out, by its state or its reason
    "settling": "{name} is settling",
    "loud": "{name} is touching but noisy",
    "hum": "{name} is not touching skin (mostly mains hum)",
    "railed": "{name} is at the limit of its range",
    "flat": "{name} gives a flat signal",
    "floating": "{name} is not connected",
}
NO_SENSOR = "No sensor is touching skin. Is the headband on?"
_LEVEL_COLOUR = {"full": GREEN, "reduced": GREEN, "one_forehead": YELLOW, "none": RED}
SIGNAL_TEXTS = {  # contracts/cli.md: the Signal line names the signal, never the person
    "no_blinks": "blinks: not available",
    "tension": "muscle activity in the signal",
    "moving": "head movement",
    "unknown": "movement: unknown",
}


def _out_text(view: SensorView) -> str:
    why = view.reading.why if view.reading is not None else ""
    key = "settling" if view.shown == "settling" else why
    return SENSOR_TEXTS.get(key, "{name} is waiting").format(name=view.name)


def _coverage_pieces(s: Screen) -> list[tuple[str, Text]]:
    """The coverage as pieces that are never broken: its plain words and how they are drawn.
    Colour goes on the level word and on sensor names only."""
    if s.coverage is None:
        return [("waiting", Text("waiting", style=DIM))]
    level = COVERAGE_WORDS[s.coverage.level]
    word, colon, rest = level.partition(":")
    pieces = [
        (
            level,
            Text.assemble((word, f"bold {_LEVEL_COLOUR[s.coverage.level]}"), (colon + rest, INK)),
        )
    ]
    by = {v.name: v for v in s.sensors}
    if s.sensors and all(v.shown == "none" for v in s.sensors):
        return [*pieces, (NO_SENSOR, Text(NO_SENSOR, style=f"bold {INK}"))]
    for name in s.coverage.out:
        view = by.get(name)
        if view is None:
            continue
        text = _out_text(view)
        colour = _EEG[view.shown][0]
        pieces.append((text, Text.assemble((name, f"bold {colour}"), (text[len(name) :], INK))))
    return pieces


def _signal_pieces(s: Screen) -> list[tuple[str, Text]]:
    """The Signal line's pieces; no quality colour, since they grade nothing."""
    if s.signal is None:
        return [("waiting", Text("waiting", style=DIM))]
    marks = s.signal
    if marks.blinks is None:
        words = [SIGNAL_TEXTS["no_blinks"]]
    else:
        words = [f"{marks.blinks} blink{'' if marks.blinks == 1 else 's'}"]
    if marks.tension:
        words.append(SIGNAL_TEXTS["tension"])
    if marks.movement in ("moving", "unknown"):
        words.append(SIGNAL_TEXTS[marks.movement])
    return [(w, Text(w, style=INK)) for w in words]


def _block(label: str, pieces: list[tuple[str, Text]], width: int) -> Text:
    """` <label>  <piece> · <piece>`, broken between pieces (never inside one) to fit `width`."""
    out, line = Text(), Text.assemble((f" {label:<8}  ", DIM))
    indent = " " * line.cell_len
    first = True
    for _, piece in pieces:
        joint = Text("") if first else Text(" · ", style=DIM)
        if not first and line.cell_len + joint.cell_len + piece.cell_len > width:
            out.append_text(line)
            out.append("\n")
            line, joint = Text(indent), Text("")
        line.append_text(joint)
        line.append_text(piece)
        first = False
    out.append_text(line)
    out.no_wrap, out.overflow = True, "ellipsis"
    return out


def coverage_line(s: Screen, width: int) -> Text:
    """`Coverage  <level> · <each sensor that is out>`."""
    return _block("Coverage", _coverage_pieces(s), width)


def signal_line(s: Screen, width: int) -> Text:
    """`Signal    <blinks> · <marks of the newest second>`."""
    return _block("Signal", _signal_pieces(s), width)


# Streams ---------------------------------------------------------------------------------------


def _pct(row: StreamRow) -> str:
    return f"{100 * row.rate / row.nominal:.0f}%" if row.seen else "waiting"


def _streams_line(s: Screen, width: int) -> Text:
    pieces: list[Text] = []
    for row in s.streams:
        if row.seen:
            pct = 100 * row.rate / row.nominal
            colour = GREEN if pct >= GOOD_PCT else YELLOW if pct >= FAIR_PCT else RED
        else:
            colour = DIM
        pieces.append(
            Text.assemble(
                (f"{row.name} ", "bold"),
                (f"{row.rate:.0f}/{row.nominal:.0f} ", INK),
                (_pct(row), f"bold {colour}"),
            )
        )
    pieces.append(Text.assemble(("gaps ", DIM), (str(s.gaps), "bold")))
    if s.recording:
        pieces.append(Text.assemble(("markers ", DIM), (str(s.markers), "bold")))
    if s.glare:
        pieces.append(Text("optics: too much light", style=f"bold {RED}"))
    out, line = Text(), Text(" ")
    for piece in pieces:  # break between pieces, never inside one
        joint = Text(" · ", style=DIM) if line.plain.strip() else Text("")
        if line.cell_len + joint.cell_len + piece.cell_len > width and line.plain.strip():
            out.append_text(line)
            out.append("\n")
            line, joint = Text(" "), Text("")
        line.append_text(joint)
        line.append_text(piece)
    out.append_text(line)
    out.no_wrap, out.overflow = True, "ellipsis"
    return out


# Guide -----------------------------------------------------------------------------------------


def _left(seconds: float) -> str:
    whole = max(math.ceil(seconds - 1e-9), 0)
    return f"{whole // 60}:{whole % 60:02d} left"


@dataclass(frozen=True)
class GuideView:
    """What we're doing, the instruction right now with its countdown, and the whole timeline."""

    guide: Guide
    elapsed: float
    width: int = WIDE

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        g = glyphs_for(options)
        guide, elapsed = self.guide, self.elapsed
        text, left = guide.current(elapsed)
        now = Table.grid(expand=True)
        now.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
        now.add_column(width=12, justify="right", no_wrap=True)
        now.add_row(
            Text.assemble(
                (" NOW ", f"bold black on {CLI_ORANGE}"), " ", (text, f"bold {CLI_ORANGE}")
            ),
            Text(_left(left), style="bold"),
        )
        bar = ProgressBar(
            total=guide.duration, completed=min(elapsed, guide.duration), complete_style=CLI_ORANGE
        )
        style = {"done": (g.done, "dim"), "now": (g.now, f"bold {CLI_ORANGE}")}
        steps = Table.grid(padding=(0, 1))
        steps.add_column(no_wrap=True)
        steps.add_column(no_wrap=True)
        steps.add_column(no_wrap=True, overflow="ellipsis")
        for at, step, state in guide.timeline(elapsed):
            mark, look = style.get(state, (g.next, "bold"))
            steps.add_row(mark, f"{int(at) // 60}:{int(at) % 60:02d}", step, style=look)
        yield Panel(
            Group(now, bar, Text(""), steps),  # the blank line keeps the first step off the bar
            title=guide.title or "Guided session",
            subtitle=guide.clock(elapsed),
            title_align="left",
            subtitle_align="right",
            border_style=CLI_ORANGE,
            box=box.SQUARE,
            width=self.width,
        )


def guide_panel(guide: Guide, elapsed: float, *, width: int = WIDE) -> GuideView:
    return GuideView(guide, elapsed, width)


def lines(renderable: RenderableType, width: int, **console: object) -> list[str]:
    """The plain text lines `renderable` draws at `width` columns (for tests and screenshots)."""
    settings: dict[str, object] = {"legacy_windows": False, "color_system": None, **console}
    out = Console(width=width, file=io.StringIO(), **settings)  # type: ignore[arg-type]
    with out.capture() as captured:
        out.print(renderable)
    return captured.get().splitlines()
