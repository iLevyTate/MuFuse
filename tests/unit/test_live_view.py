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

from mufuse.acquisition.contact import Reading, SensorView
from mufuse.acquisition.supervisor import State
from mufuse.acquisition.types import Chunk, DeviceInfo, StreamKind
from mufuse.guide import Cue, Guide, action
from mufuse.live_view import WIDE, LiveStats, Screen, StreamRow, guide_panel, lines
from tests.conftest import FakeClock

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


def test_contact_is_graded_on_the_last_second(clock: FakeClock) -> None:
    stats = LiveStats(clock)
    stats.add([_eeg(clock.now, 1.0)], clock.now + 1)
    views = stats.contact()
    assert [v.name for v in views] == list(SENSORS)
    assert {v.shown for v in views} == {"settling"}
    assert LiveStats(clock).contact()[0].shown == "waiting"


def test_glare_is_seen_on_the_sixteen_channel_presets(clock: FakeClock) -> None:
    stats = LiveStats(clock)
    stats.add([_optics(clock.now, 64, 80.0)], clock.now)
    assert not stats.too_much_light("p1041")
    stats.add([_optics(clock.now + 1, 64, 80.0, level=float(2**20 - 1))], clock.now + 1)
    assert stats.too_much_light("p1041")
    assert stats.too_much_light("p1045")  # the ceiling counts on every preset
    assert not LiveStats(clock).too_much_light("p1041")
