"""Calibration tables and threshold suggestions from the numbers a sitting saved.

Input is what the judges filed in `Result.measures`, per check id: P0's still phase, H8's rest,
lift, clench and blink phases, H4's whole recording and F1's optics levels. Output is text for
the acceptance report.

Suggestions only. Nothing here changes `signal_check.py`: the channel check is tuned in feature
002, in a reviewed commit that cites the run and is checked with `--rejudge`.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from mufuse.acceptance import AMBIENT_WIRE, CARDIAC_HZ, EEG_RANGE_UV, LABELS, RAIL_MARGIN
from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.signal_check import FLAT_UV, NOISY_UV, RAIL_UV
from mufuse.acquisition.types import StreamKind

Measures = Mapping[str, Mapping[str, float]]  # check id -> the numbers its judge saved

_CHANNELS = ATHENA_STREAMS[StreamKind.EEG].channel_names[:4]
_FRONT, _EARS = ("AF7", "AF8"), ("TP9", "TP10")
# (check, the phase's name in its measures, how the report calls it)
_PHASES = (
    ("P0", "still", "P0 sitting still"),
    ("H8", "rest", "H8 at rest"),
    ("H8", "lift", "H8 left ear sensor lifted"),
    ("H8", "clench", "H8 jaw clenched"),
    ("H8", "blink", "H8 blinking"),
    ("H4", "whole", "H4 whole recording (worn or on the desk)"),
)
_OPTICS_ROLES = ("red", "ambient", "730 nm", "850 nm")  # BrainFlow wire order, four rows each
_OPTICS_SCALE = 32768.0  # OpenMuse and Mind Monitor show BrainFlow's raw counts divided by this
MISSING = "-"


@dataclass(frozen=True)
class Table:
    title: str
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    note: str = ""


def _uv(value: float) -> str:
    return f"{value:.0f}" if abs(value) >= 2 else f"{value:.1f}"


def _pct(share: float) -> str:
    return f"{100 * share:.0f}"


def _spread(m: Mapping[str, float], at: str) -> str:
    return " / ".join(_uv(m[f"{at}.spread{p}_uv"]) for p in ("_p05", "", "_p95"))


def _labels(m: Mapping[str, float], at: str) -> str:
    return " / ".join(_pct(m[f"{at}.{label}_share"]) for label in LABELS)


def _plain(m: Mapping[str, float], at: str) -> str:
    return f"{_uv(m[f'{at}.std_uv'])} / {_uv(m[f'{at}.ptp_uv'])} / {_pct(m[f'{at}.rail_share'])}"


def _hum(m: Mapping[str, float], at: str) -> str:
    return f"{_pct(m[f'{at}.mains_50hz_share'])} / {_pct(m[f'{at}.mains_60hz_share'])}"


_EEG_TABLES: tuple[tuple[str, Callable[[Mapping[str, float], str], str]], ...] = (
    ("EEG robust spread per 2 s window, µV: 5th percentile / median / 95th percentile", _spread),
    (
        "What the live channel check called those windows, % of windows: " + " / ".join(LABELS),
        _labels,
    ),
    (
        "Plain numbers: median std µV / median peak-to-peak µV / % of samples within "
        f"{RAIL_MARGIN:.0%} of full scale",
        _plain,
    ),
    ("Mains hum, % of the EEG power above 1 Hz: 50 Hz / 60 Hz", _hum),
)


def _cell(cell: Callable[[Mapping[str, float], str], str], m: Mapping[str, float], at: str) -> str:
    try:
        return cell(m, at)
    except KeyError:
        return MISSING


def tables(measures: Measures) -> list[Table]:
    """The per-channel EEG tables, one row per phase that saved numbers, then F1's optics."""
    phases = [
        (measures[check], name, title)
        for check, name, title in _PHASES
        if any(key.startswith(f"{name}.") for key in measures.get(check, {}))
    ]
    made: list[Table] = []
    if phases:
        for title, cell in _EEG_TABLES:
            rows = tuple(
                (phase, *(_cell(cell, m, f"{name}.{ch}") for ch in _CHANNELS))
                for m, name, phase in phases
            )
            made.append(Table(title, ("Phase", *_CHANNELS), rows))
    f1 = measures.get("F1", {})
    if "on_head.OPT1.median" in f1:
        made.append(_optics(f1))
    return made


def _optics(f1: Mapping[str, float]) -> Table:
    def level(m: Mapping[str, float], at: str) -> str:
        return f"{m[at]:.0f}"

    def rise(m: Mapping[str, float], row: str) -> str:
        lit = min(m[f"room_light.{row}.median"], m[f"light_again.{row}.median"])
        return f"{lit - m[f'dark.{row}.median']:+.0f}"

    def pulse(m: Mapping[str, float], row: str) -> str:
        return f"{_pct(m[f'on_head.{row}.pulse_share'])}%"

    rows: list[tuple[str, ...]] = []
    for n in range(1, 17):
        row = f"OPT{n}"
        levels = (
            _cell(level, f1, f"{phase}.{row}.median")
            for phase in ("on_head", "room_light", "dark", "light_again")
        )
        role = _OPTICS_ROLES[(n - 1) // 4]
        rows.append((row, role, *levels, _cell(rise, f1, row), _cell(pulse, f1, row)))
    header = (
        "Row", "Wire role", "On head", "Room light", "Covered", "Light again",
        "Room light over covered", "Pulse share on head",
    )  # fmt: skip
    note = "BrainFlow raw counts, rows in wire order. OpenMuse and Mind Monitor show counts ÷ 32768"
    covered = [f1[key] for n in AMBIENT_WIRE if (key := f"dark.OPT{n}.median") in f1]
    if len(covered) == len(AMBIENT_WIRE):
        pedestal = sum(covered) / len(covered)
        note += (
            f": the covered level of OPT{AMBIENT_WIRE[0]} to OPT{AMBIENT_WIRE[-1]}, about "
            f"{pedestal:.0f} counts here, reads about {pedestal / _OPTICS_SCALE:.1f} there"
        )
    note += (
        ". The role is the one expected for wire order; F1's outcome says whether this headband "
        "agrees. Pulse share: the part of a row's 0.1 to 10 Hz power between "
        f"{CARDIAC_HZ[0]:g} and {CARDIAC_HZ[1]:g} Hz, where a heartbeat shows."
    )
    return Table("F1 optics, median counts per phase", header, tuple(rows), note)


# Suggestions ---------------------------------------------------------------------------------
# Each takes the measures per check and raises KeyError when a number it needs was not saved.


def _extreme(
    m: Mapping[str, float], phase: str, what: str, channels: tuple[str, ...], *, top: bool
) -> tuple[float, str]:
    """The highest (or lowest) of one number over `channels`, and the channel it was on."""
    values = [(m[f"{phase}.{ch}.{what}"], ch) for ch in channels]
    return max(values, key=lambda v: v[0]) if top else min(values, key=lambda v: v[0])


def _noisy(measures: Measures) -> str:
    h8 = measures["H8"]
    low, low_ch = _extreme(h8, "rest", "spread_p95_uv", _CHANNELS, top=True)
    high, high_ch = _extreme(h8, "clench", "spread_p05_uv", _EARS, top=False)
    head = f"Noisy threshold (NOISY_UV, now {NOISY_UV:.0f} µV): "
    if high <= low or low <= 0:
        return (
            f"{head}not separable. At rest the spread reached {_uv(low)} µV ({low_ch}) in the top "
            f"5% of windows, and with the jaw clenched it was down at {_uv(high)} µV ({high_ch}) "
            "in the bottom 5%: no single threshold on the spread tells the two apart in this run."
        )
    mid = math.sqrt(low * high)
    text = (
        f"{head}at rest the spread stayed under {_uv(low)} µV ({low_ch}) in 95% of windows; "
        f"with the jaw clenched it stayed above {_uv(high)} µV ({high_ch}) in 95% of windows. "
        f"A threshold of about {mid:.0f} µV, the geometric midpoint, would separate the two."
    )
    if high <= NOISY_UV:
        text += (
            " The threshold in force is above that clench: a clench this weak would still read ok."
        )
    elif low >= NOISY_UV:
        text += (
            " The threshold in force is under that rest level: windows at rest would read noisy."
        )
    else:
        text += (
            f" The threshold in force lies inside that gap, {_uv(NOISY_UV - low)} µV above rest "
            f"and {_uv(high - NOISY_UV)} µV under the clench."
        )
    blink, blink_ch = _extreme(h8, "blink", "spread_p95_uv", _FRONT, top=True)
    if blink > mid:
        text += (
            f" While blinking the spread reached {_uv(blink)} µV ({blink_ch}): a blink would "
            "read noisy at that threshold."
        )
    else:
        text += f" Blinks stayed under it: {_uv(blink)} µV at most ({blink_ch})."
    if "P0" in measures:
        still, still_ch = _extreme(measures["P0"], "still", "spread_p95_uv", _CHANNELS, top=True)
        if still > mid:
            text += (
                f" P0's still phase reached {_uv(still)} µV ({still_ch}), above that midpoint: "
                "the fit changed between the two checks, or rest is not steady."
            )
    return text


def _rail(measures: Measures) -> str:
    h8 = measures["H8"]
    near = round((1 - RAIL_MARGIN) * EEG_RANGE_UV, -1)
    return (
        f"Rail threshold (RAIL_UV, now {RAIL_UV:.0f} µV, within 2% of the ±{EEG_RANGE_UV:.0f} µV "
        "full scale; it was 1000 µV, which cannot be reached). The channel check is still given "
        "centred windows, where a channel stuck at the rail reads flat; the live contact view "
        f"counts railed samples before centring. Within {RAIL_MARGIN:.0%} of full scale (beyond "
        f"about {near:.0f} µV): {_pct(h8['lift.TP9.rail_share'])}% of the lifted TP9 samples, "
        f"{_pct(h8['rest.TP9.rail_share'])}% at rest."
    )


def _lifted(measures: Measures) -> str:
    h8 = measures["H8"]
    shares = {label: h8[f"lift.TP9.{label}_share"] for label in LABELS}
    others = ", ".join(f"{label} {_pct(s)}%" for label, s in shares.items() if label != "ok")
    numbers = (
        f"the robust spread was {_uv(h8['lift.TP9.spread_uv'])} µV against "
        f"{_uv(h8['rest.TP9.spread_uv'])} µV at rest, the plain std {_uv(h8['lift.TP9.std_uv'])} "
        f"µV against {_uv(h8['rest.TP9.std_uv'])} µV"
    )
    if shares["ok"] >= 0.5:
        return (
            "Lifted sensor: with the left ear sensor off the skin the channel check still called "
            f"TP9 ok in {_pct(shares['ok'])}% of windows ({others}); {numbers}. Telling a lifted "
            "sensor needs a measure other than the robust spread."
        )
    return (
        "Lifted sensor: with the left ear sensor off the skin the channel check called TP9 ok "
        f"in {_pct(shares['ok'])}% of windows ({others}); {numbers}."
    )


def _flat(measures: Measures) -> str:
    low, ch = _extreme(measures["H8"], "rest", "spread_p05_uv", _CHANNELS, top=False)
    head = f"Flat threshold (FLAT_UV, now {FLAT_UV:.0f} µV): the lowest spread at rest was"
    if low > FLAT_UV:
        return f"{head} {_uv(low)} µV ({ch}), clear of it. No change suggested."
    return f"{head} {_uv(low)} µV ({ch}): rest windows on that channel read flat."


def suggestions(measures: Measures) -> list[str]:
    """One line per channel-check threshold, from H8's phases. Nothing is applied."""
    lines: list[str] = []
    for suggest in (_noisy, _rail, _flat, _lifted):
        try:
            lines.append(suggest(measures))
        except KeyError:
            continue  # that number was not saved: a check that failed early or was skipped
    return lines or ["H8 saved no numbers, so there is nothing to suggest thresholds from."]
