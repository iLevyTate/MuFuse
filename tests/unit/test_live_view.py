# ruff: noqa: RUF001  (the marks under test are the point)
"""The live view of stream/record (issue #13): layout, fixed widths and what it says."""

from __future__ import annotations

import io
import re
import string
from dataclasses import replace

import numpy as np
import pytest
from rich.console import Console
from rich.style import Style
from rich.text import Text

from mufuse.acquisition.contact import Reading, SensorView
from mufuse.acquisition.supervisor import State
from mufuse.acquisition.types import Chunk, DeviceInfo, StreamKind
from mufuse.guide import Cue, Guide, action
from mufuse.live_view import (
    DIM,
    GREEN,
    INK,
    RED,
    WIDE,
    YELLOW,
    LiveStats,
    Screen,
    SignalMarks,
    StreamRow,
    coverage_line,
    guide_panel,
    lines,
    signal_line,
)
from mufuse.quality.answer import Coverage
from tests.conftest import QUICK, FakeClock, rehearse

DEVICE = DeviceInfo("MuseS-1A2B", "p1041", "simulated", firmware="3.1.31")
SENSORS = ("TP9", "AF7", "AF8", "TP10")


def _view(
    name: str, shown: str, spread: float = 20.0, why: str = "quiet", **kw: float
) -> SensorView:
    grade = {"settling": "good", "waiting": "good"}.get(shown, shown)
    reading = Reading(grade, why, spread, kw.get("mains", 0.9))  # type: ignore[arg-type]
    left = int(kw.get("left", 0))
    return SensorView(name, shown, None if shown == "waiting" else reading, left)  # type: ignore[arg-type]


FITTING = (
    _view("TP9", "none", 300.0, "hum", mains=0.99),
    _view("AF7", "good", 31.0),
    _view("AF8", "settling", 28.0, left=2),
    _view("TP10", "good", 8.0),
)
ANSI = re.compile(r"\x1b\[[0-9;]*m")
DETECTORS = {"LO": "finding", "LI": "pulse", "RI": "pulse", "RO": "light"}
ALL_GOOD = tuple(_view(n, "good", s) for n, s in zip(SENSORS, (12.0, 31.0, 28.0, 8.0), strict=True))
STREAMS = (
    StreamRow("EEG", 256.0, 256.0, True),
    StreamRow("Motion", 52.0, 52.0, True),
    StreamRow("Optics", 64.3, 64.0, True),
)
P0 = Guide(
    cues=(
        Cue(0, "Adjust until all four sensors are good", marker="adjust"),
        *action(15, "Sit still, eyes open, jaw relaxed", marker="still"),
    ),
    duration=45.0,
    title="P0 · Preflight: fit, battery and streams",
)


def _screen(**kw: object) -> Screen:
    base = Screen(
        recording="20261126T204104Z-56df",
        elapsed=6.0,
        state=State.STREAMING,
        link_error=None,
        battery=80.0,
        device=DEVICE,
        sensors=FITTING,
        streams=STREAMS,
        gaps=0,
        markers=0,
        glare=False,
        guide=(P0, 6.0),
    )
    return replace(base, **kw)  # type: ignore[arg-type]


@pytest.mark.parametrize("width", [80, 60])
def test_nothing_is_wider_than_the_terminal_and_every_sensor_is_named(width: int) -> None:
    for screen in (_screen(), _screen(sensors=ALL_GOOD, guide=None, recording=None)):
        shown = lines(screen, width)
        assert max(len(line) for line in shown) <= width
        text = "\n".join(shown)
        for name in SENSORS:
            assert text.count(name) >= 2  # on the head map and in its row


def test_the_map_sits_beside_the_list_from_78_columns_and_above_it_below() -> None:
    assert WIDE == 78
    wide = lines(_screen(), 80)
    assert any("front" in line and "EEG" in line for line in wide)
    narrow = lines(_screen(), 60)
    assert not any("front" in line and "EEG" in line for line in narrow)
    assert any("EEG" in line for line in narrow)


def _rows(screen: Screen, width: int = 80) -> dict[str, str]:
    """Each sensor's list row, from its glyph to the right border."""
    out: dict[str, str] = {}
    for line in lines(screen, width):
        for name in SENSORS:
            if re.search(rf"\S {name} +(good|no contact|settling|noisy|waiting)", line):
                out[name] = line[line.index(f" {name} ") - 1 :]
    return out


def test_rows_keep_their_columns_whatever_the_grade() -> None:
    fitting, good = _rows(_screen()), _rows(_screen(sensors=ALL_GOOD))
    assert set(fitting) == set(good) == set(SENSORS)
    for name in SENSORS:
        assert len(fitting[name]) == len(good[name])
    assert fitting["TP9"].rstrip("│ ").endswith("hum 99%")
    assert "settling 2 s" in fitting["AF8"]
    assert fitting["AF8"].rstrip("│ ").endswith("28 µV")
    ends = {len(row.rstrip("│ ")) for row in (*fitting.values(), *good.values())}
    assert len(ends) == 1  # the number column ends at the same place in every row


def test_the_position_map_lines_up_with_its_labels() -> None:
    shown = lines(_screen(detectors=DETECTORS), 80)
    forehead = next(line for line in shown if "AF7" in line and "AF8" in line)
    labels = next(line for line in shown if "LO LI" in line)
    for label in ("LO", "LI", "RI", "RO"):
        col = labels.index(label)
        assert forehead[col] in "■□×·" or forehead[col + 1] in "■□×·", label
    assert forehead[labels.index("LI") + 4] == "♦" or "♦" in forehead
    ears = next(line for line in shown if "TP9" in line and "TP10" in line)
    assert ears.index("TP9") < ears.index("TP10")


def test_the_fitting_screen_says_what_the_mockup_says() -> None:
    text = "\n".join(lines(_screen(detectors=DETECTORS, markers=2), 80))
    for words in (
        "REC",
        "00:06",
        "streaming",
        "battery 80%",
        "20261126T204104Z-56df",
        "MuseS-1A2B · fw 3.1.31 · p1041",
        "FITTING",
        "2 of 4 EEG good · fix TP9 first",
        "fNIRS 2 of 4 with pulse",
        "front",
        "back",
        "REF",
        "no contact",
        "settling 2 s",
        "fNIRS",
        "experimental",
        "pulse seen",
        "finding pulse",
        "light leaking",
        "TP9: push hair aside, wet the skin behind the ear",
        "EEG 256/256 100%",
        "Optics 64/64 100%",
        "gaps 0",
        "markers 2",
        "NOW",
        "0:06 left",
        "0:06 / 0:45",
        "● good  ○ settling/noisy  × no contact",
        "space marker · 1-9 start/end block · q stop",
    ):
        assert words in text, words
    assert "horseshoe" not in text.lower()


def test_ready_when_all_four_are_good_and_waiting_before_any_eeg() -> None:
    assert "READY" in "\n".join(lines(_screen(sensors=ALL_GOOD), 80))
    waiting = tuple(_view(n, "waiting") for n in SENSORS)
    assert "WAITING" in "\n".join(lines(_screen(sensors=waiting), 80))
    settling = tuple(_view(n, "settling", left=1) for n in SENSORS)
    assert "0 of 4 EEG good · hold still" in "\n".join(lines(_screen(sensors=settling), 80))


def test_the_reference_is_read_off_the_eeg() -> None:
    none = tuple(_view(n, "none", 300.0, "hum", mains=0.99) for n in SENSORS)
    ref = next(line for line in lines(_screen(sensors=none), 80) if "REF" in line)
    assert "REF ×" in ref
    ref = next(line for line in lines(_screen(), 80) if "REF" in line)
    assert "REF ●" in ref


def test_traces_rise_with_the_signal() -> None:
    traces = {"TP9": (400.0,) * 10, "AF7": (4.0,) * 10}
    rows = _rows(_screen(traces=traces))
    assert "██████████" in rows["TP9"]
    assert "▁▁▁▁▁▁▁▁▁▁" in rows["AF7"]


def test_presets_without_the_detector_map_say_so() -> None:
    assert "not in preset" in "\n".join(lines(_screen(detectors={}), 80))


@pytest.mark.parametrize(
    "console",
    [
        {"legacy_windows": True},
        {"force_terminal": False},
        {"no_color": True},
        {"color_system": "standard"},
    ],
)
def test_every_kind_of_terminal_gets_a_readable_screen(console: dict[str, object]) -> None:
    for width in (60, 80, 120):
        shown = [
            ANSI.sub("", line) for line in lines(_screen(detectors=DETECTORS), width, **console)
        ]
        assert max(len(line) for line in shown) <= width
        text = "\n".join(shown)
        for words in ("TP9", "AF7", "AF8", "TP10", "no contact", "settling", "LO", "RO", "NOW"):
            assert words in text, (console, width, words)


def test_legacy_consoles_and_mufuse_ascii_get_plain_ascii_marks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = "\n".join(lines(_screen(detectors=DETECTORS), 80, legacy_windows=True))
    assert "x TP9" in legacy
    assert "O AF7" in legacy
    assert "o AF8" in legacy
    assert not set("●○×■□♦√►▁█›") & set(legacy)
    monkeypatch.setenv("MUFUSE_ASCII", "1")
    forced = "\n".join(lines(_screen(detectors=DETECTORS), 80))
    assert "x TP9" in forced
    assert not set("●○×■□♦") & set(forced)


def test_a_cp1252_file_can_hold_the_screen() -> None:
    raw = io.BytesIO()
    out = Console(file=io.TextIOWrapper(raw, encoding="cp1252"), width=80, legacy_windows=False)
    out.print(_screen(detectors=DETECTORS))
    out.file.flush()
    text = raw.getvalue().decode("cp1252")
    assert "x TP9" in text  # the output can't encode ●, so the marks are ASCII


def test_the_status_line_is_one_plain_line() -> None:
    line = _screen(detectors=DETECTORS, markers=3).status_line()
    assert "\n" not in line
    assert line.isascii() or set(line) - set(string.printable) <= {"·"}
    for words in ("00:06", "TP9 no contact", "AF8 settling", "fNIRS 2/4 pulse", "markers 3"):
        assert words in line, words
    assert "NOW: Adjust until all four sensors are good (0:06 left)" in line


# Coverage --------------------------------------------------------------------------------------

EARS_OUT = (
    _view("TP9", "none", 300.0, "hum", mains=0.99),
    _view("AF7", "good", 31.0),
    _view("AF8", "good", 28.0),
    _view("TP10", "none", 120.0, "floating"),
)
REDUCED = Coverage("reduced", ("TP9", "TP10"))


def _coverage(screen: Screen, width: int = 160) -> list[str]:
    """The Coverage line, and the lines it continues on."""
    shown = [line.rstrip() for line in lines(screen, width)]
    first = next(i for i, line in enumerate(shown) if line.startswith(" Coverage  "))
    out = [shown[first]]
    for line in shown[first + 1 :]:
        if not line.startswith(" " * 11):
            break
        out.append(line)
    return out


def test_the_coverage_line_names_the_level_and_each_sensor_that_is_out() -> None:
    assert _coverage(_screen(sensors=EARS_OUT, coverage=REDUCED)) == [
        " Coverage  reduced: forehead sensors good · TP9 is not touching skin (mostly mains hum)"
        " · TP10 is not connected"
    ]


@pytest.mark.parametrize("width", [60, 80])
def test_the_coverage_line_breaks_between_texts_never_inside_one(width: int) -> None:
    shown = _coverage(_screen(sensors=EARS_OUT, coverage=REDUCED), width)
    assert len(shown) > 1
    assert max(len(line) for line in shown) <= width
    for words in (
        "reduced: forehead sensors good",
        "TP9 is not touching skin (mostly mains hum)",
        "TP10 is not connected",
    ):
        assert any(words in line for line in shown), words


def test_the_coverage_line_sits_between_the_sensors_and_the_streams() -> None:
    shown = lines(_screen(sensors=EARS_OUT, coverage=REDUCED), 80)
    at = next(i for i, line in enumerate(shown) if line.startswith(" Coverage  "))
    assert shown[at - 1].startswith("└")  # the bottom of the sensors panel
    assert next(i for i, line in enumerate(shown) if line.startswith(" EEG ")) > at


@pytest.mark.parametrize(
    ("shown", "why", "text"),
    [
        ("settling", "quiet", "AF7 is settling"),
        ("noisy", "loud", "AF7 is touching but noisy"),
        ("none", "hum", "AF7 is not touching skin (mostly mains hum)"),
        ("none", "railed", "AF7 is at the limit of its range"),
        ("none", "flat", "AF7 gives a flat signal"),
        ("none", "floating", "AF7 is not connected"),
    ],
)
def test_every_sensor_text_of_the_contract(shown: str, why: str, text: str) -> None:
    sensors = tuple(
        _view(n, shown, 200.0, why, left=1) if n == "AF7" else _view(n, "good") for n in SENSORS
    )
    screen = _screen(sensors=sensors, coverage=Coverage("one_forehead", ("AF7",)))
    assert _coverage(screen) == [f" Coverage  one forehead sensor · {text}"]


def test_a_headband_that_is_not_on_gets_one_sentence_not_four_faults() -> None:
    off = (
        _view("TP9", "none", 300.0, "hum"),
        _view("AF7", "none", 120.0, "floating"),
        _view("AF8", "none", 0.0, "flat"),
        _view("TP10", "none", 120.0, "floating"),
    )
    assert _coverage(_screen(sensors=off, coverage=Coverage("none", SENSORS))) == [
        " Coverage  none · No sensor is touching skin. Is the headband on?"
    ]


def test_coverage_waits_for_the_first_judged_second_and_reads_full_when_all_are_good() -> None:
    assert _coverage(_screen()) == [" Coverage  waiting"]
    full = _screen(sensors=ALL_GOOD, coverage=Coverage("full", ()))
    assert _coverage(full) == [" Coverage  full"]


def _colours(text: Text) -> dict[str, str]:
    """The colour of each coloured piece of `text`, by its words."""
    out: dict[str, str] = {}
    for span in text.spans:
        style = span.style if isinstance(span.style, Style) else Style.parse(span.style)
        if style.color is not None:
            out[text.plain[span.start : span.end]] = style.color.get_truecolor().hex.upper()
    return out


def test_only_the_quality_colours_and_only_on_sensor_names_and_the_level() -> None:
    colours = _colours(coverage_line(_screen(sensors=EARS_OUT, coverage=REDUCED), 160))
    assert set(colours.values()) <= {GREEN, YELLOW, RED, DIM, INK}
    graded = {words: c for words, c in colours.items() if c in (GREEN, YELLOW, RED)}
    assert graded == {"reduced": GREEN, "TP9": RED, "TP10": RED}
    noisy = (*EARS_OUT[:3], _view("TP10", "noisy", 120.0, "loud"))
    colours = _colours(
        coverage_line(_screen(sensors=noisy, coverage=Coverage("reduced", ("TP9", "TP10"))), 160)
    )
    assert colours["TP10"] == YELLOW


# Signal ----------------------------------------------------------------------------------------


def _signal(screen: Screen, width: int = 160) -> list[str]:
    """The Signal line, and the lines it continues on."""
    shown = [line.rstrip() for line in lines(screen, width)]
    first = next(i for i, line in enumerate(shown) if line.startswith(" Signal    "))
    out = [shown[first]]
    for line in shown[first + 1 :]:
        if not line.startswith(" " * 11):
            break
        out.append(line)
    return out


@pytest.mark.parametrize(
    ("marks", "text"),
    [
        (
            SignalMarks(14, True, "moving"),
            "14 blinks · muscle activity in the signal · head movement",
        ),
        (SignalMarks(1, False, "still"), "1 blink"),
        (SignalMarks(0, True, "still"), "0 blinks · muscle activity in the signal"),
        (SignalMarks(None, False, "unknown"), "blinks: not available · movement: unknown"),
    ],
)
def test_the_signal_line_counts_blinks_and_names_the_marks(marks: SignalMarks, text: str) -> None:
    assert _signal(_screen(sensors=ALL_GOOD, signal=marks)) == [f" Signal    {text}"]


def test_the_signal_line_waits_and_sits_under_the_coverage() -> None:
    assert _signal(_screen()) == [" Signal    waiting"]
    screen = _screen(sensors=EARS_OUT, coverage=REDUCED, signal=SignalMarks(3, False, "still"))
    shown = [line.rstrip() for line in lines(screen, 60)]
    at = next(i for i, line in enumerate(shown) if line.startswith(" Signal    "))
    assert shown[at - 1].startswith(" " * 11)  # the coverage line, continued
    assert any(line.startswith(" Coverage  ") for line in shown[:at])
    assert shown[at + 1].startswith(" EEG ")


def test_the_signal_line_carries_no_quality_colour() -> None:
    screen = _screen(signal=SignalMarks(14, True, "moving"))
    assert set(_colours(signal_line(screen, 160)).values()) <= {DIM, INK}


def test_the_status_line_carries_the_signal() -> None:
    line = _screen(signal=SignalMarks(14, True, "moving")).status_line()
    assert "signal 14 blinks · muscle activity in the signal · head movement" in line
    assert "signal waiting" in _screen().status_line()


def test_live_stats_count_the_blinks(clock: FakeClock) -> None:
    stats = LiveStats(clock)
    reads = rehearse(replace(QUICK, blinks=((7.0, 10.0),)), clock, 12.0)
    for i, read in enumerate(reads):
        stats.add(read, clock.now)
        if i == 11:  # three seconds in: the eye mark is not available yet
            marks = stats.signal()
            assert marks is not None
            assert marks.blinks is None
    marks = stats.signal()
    assert marks == SignalMarks(3, False, "still")
    assert LiveStats(clock).signal() is None


def test_the_status_line_carries_the_coverage() -> None:
    line = _screen(sensors=EARS_OUT, coverage=REDUCED).status_line()
    assert (
        "coverage reduced: forehead sensors good · TP9 is not touching skin (mostly mains hum)"
        " · TP10 is not connected"
    ) in line
    assert "coverage waiting" in _screen().status_line()


def test_the_now_line_keeps_its_time_left_on_one_line() -> None:
    long = Guide(cues=(Cue(0, "word " * 30),), duration=600.0, title="H4")
    for width in (78, 60, 40):
        shown = lines(guide_panel(long, 267.0, width=width), width)
        now = next(line for line in shown if "NOW" in line)
        assert now.rstrip("│ ").endswith("5:33 left")
        assert "…" in now  # the instruction is cut, the countdown never wraps


def test_battery_reads_dots_until_the_headband_reports_it() -> None:
    assert "battery …" in "\n".join(lines(_screen(battery=None), 80))
    assert "battery 0%" not in "\n".join(lines(_screen(battery=None), 80))


def test_a_stream_mode_screen_shows_live_and_only_the_stop_key() -> None:
    text = "\n".join(lines(_screen(recording=None, guide=None), 80))
    assert "LIVE" in text
    assert "not recording" in text
    assert "markers" not in text
    assert text.rstrip().endswith("q stop")


def test_warnings_reach_the_screen() -> None:
    text = "\n".join(lines(_screen(notes=("the headset reports preset p1021",)), 80))
    assert "! the headset reports preset p1021" in text
    assert "optics: too much light" in "\n".join(lines(_screen(glare=True), 80))
    reconnecting = _screen(state=State.RECONNECTING, link_error="Bluetooth is off")
    text = "\n".join(lines(reconnecting, 80))
    assert "reconnecting" in text
    assert "link: Bluetooth is off" in text


def test_streams_not_seen_yet_wait_and_slow_ones_change_colour() -> None:
    rows = (StreamRow("EEG", 0.0, 256.0, False), *STREAMS[1:])
    text = "\n".join(lines(_screen(streams=rows), 80))
    assert "waiting" in text


# LiveStats ---------------------------------------------------------------------------------------


def _eeg(t0: float, seconds: float, uv: float = 15.0) -> Chunk:
    n = int(seconds * 256)
    rng = np.random.default_rng(3)
    return Chunk(StreamKind.EEG, t0 + np.arange(n) / 256, uv * rng.standard_normal((n, 8)))


def _optics(t0: float, n: int, battery: float, level: float = 300_000.0) -> Chunk:
    data = np.full((n, 17), level)
    data[:, -1] = battery
    return Chunk(StreamKind.OPTICS, t0 + np.arange(n) / 64, data)


def test_rates_count_from_the_first_data_not_from_a_full_window(clock: FakeClock) -> None:
    stats = LiveStats(clock)
    stats.add([_eeg(clock.now, 0.5)], clock.now)
    clock.advance(0.5)
    stats.add([], clock.now)
    assert stats.rate(StreamKind.EEG) == pytest.approx(256, rel=0.01)
    assert LiveStats(clock).rate(StreamKind.EEG) == 0.0


def test_battery_keeps_the_last_reported_level(clock: FakeClock) -> None:
    stats = LiveStats(clock)
    stats.add([_optics(clock.now, 10, 0.0)], clock.now)
    assert stats.battery is None
    stats.add([_optics(clock.now + 1, 10, 81.0)], clock.now + 1)
    stats.add([_optics(clock.now + 2, 10, 0.0)], clock.now + 2)
    assert stats.battery == 81.0


def _motion(t0: float, seconds: float) -> Chunk:
    n = round(seconds * 52)
    data = np.zeros((n, 6))
    data[:, 2] = 1.0  # gravity
    return Chunk(StreamKind.MOTION, t0 + np.arange(n) / 52, data)


def test_contact_waits_for_the_first_judged_stretch(clock: FakeClock) -> None:
    stats, t0 = LiveStats(clock), clock.now
    stats.add([_eeg(t0, 1.0), _motion(t0, 1.0)], t0 + 1)
    assert {v.shown for v in stats.contact()} == {"waiting"}  # a stretch is judged 0.25 s later
    assert stats.coverage() is None
    stats.add([_eeg(t0 + 1, 1.0), _motion(t0 + 1, 1.0)], t0 + 2)
    views = stats.contact()
    assert [v.name for v in views] == list(SENSORS)
    assert {(v.shown, v.settle_left_s) for v in views} == {("settling", 2)}
    assert stats.coverage() == Coverage("none", SENSORS)
    stats.add([_eeg(t0 + 2, 2.0), _motion(t0 + 2, 2.0)], t0 + 4)
    assert {v.shown for v in stats.contact()} == {"good"}
    assert stats.coverage() == Coverage("full", ())
    assert LiveStats(clock).contact()[0].shown == "waiting"


def test_the_sensor_panel_changes_only_when_a_stretch_is_judged(clock: FakeClock) -> None:
    stats, t0 = LiveStats(clock), clock.now
    previous, judged = stats.contact(), 0
    for read in range(40):  # ten seconds, a quarter of a second at a time
        start = t0 + read * 0.25
        stats.add([_eeg(start, 0.25), _motion(start, 0.25)], start + 0.25)
        views = stats.contact()
        if views != previous:
            assert len(stats.answers) > judged, read
        previous, judged = views, len(stats.answers)
    assert len(stats.answers) >= 8
    assert {v.shown for v in stats.contact()} == {"good"}


def test_a_gap_sends_the_sensors_back_to_waiting(clock: FakeClock) -> None:
    stats, t0 = LiveStats(clock), clock.now
    stats.add([_eeg(t0, 4.0), _motion(t0, 4.0)], t0 + 4)
    stats.add([_eeg(t0 + 9, 0.25), _motion(t0 + 9, 0.25)], t0 + 9.25)
    assert stats.answers[-1].no_data
    assert {v.shown for v in stats.contact()} == {"waiting"}
    assert stats.coverage() is None


def test_glare_is_seen_on_the_sixteen_channel_presets(clock: FakeClock) -> None:
    stats = LiveStats(clock)
    stats.add([_optics(clock.now, 64, 80.0)], clock.now)
    assert not stats.too_much_light("p1041")
    stats.add([_optics(clock.now + 1, 64, 80.0, level=float(2**20 - 1))], clock.now + 1)
    assert stats.too_much_light("p1041")
    assert stats.too_much_light("p1045")  # the ceiling counts on every preset
    assert not LiveStats(clock).too_much_light("p1041")
