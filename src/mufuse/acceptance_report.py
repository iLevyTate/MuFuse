"""The report of one hardware sitting, as markdown that is safe to paste into a public PR.

`render` works from an allowlist. From the run's rows in `acceptance.jsonl` it reads named keys
only: outcomes, attempt numbers, measures (by name, and only as numbers) and a few facts that
must look like a version or a preset to be printed. It never reads the judges' lines, session
names or notes, and every sentence in the report is written here. So a path, a user name, a
Bluetooth address or a sample cannot reach the text, whatever the rows hold.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast

from mufuse import calibration
from mufuse.acceptance import (
    AMBIENT_WIRE,
    BATTERY_MIN_PCT,
    CHANGE_FACTOR,
    COMPLETE_PCT,
    FIT_OK_SHARE,
    LIGHT_RISE,
    MIN_GAP_S,
    PRESS_LATE_S,
    RESUME_LIMIT_S,
    STOP_LATE_S,
    STREAM_MIN_PCT,
)
from mufuse.guide import READY_S

COMMAND = "uv run python scripts/hw_acceptance.py"
PASS, FAIL, SKIPPED, NOT_RUN = "PASS", "FAIL", "SKIPPED", "NOT RUN"
# Why the runner leaves a check out. A reason is printed only when it is one of these.
REASONS = (
    "skipped at the keyboard",
    "the run was ended before this check",
    "SPACE presses are only read on Windows; H6 needs a Windows terminal",
    "the hardware tests need the real headband",
    "no connection in 3 tries. Is the headband switched on? Is the Muse app on the phone closed?",
)

# In sitting order: id, what it shows, and its success criterion in specs/001's spec.md.
_CHECKS: tuple[tuple[str, str, str], ...] = (
    ("P0", "Preflight: fit, battery and streams", "-"),
    ("H8", "Channel check reacts to contact, jaw and blinks", "-"),
    (
        "H6",
        "Keyboard markers",
        "SC-004: Markers on reload sit within ±1 sample (±4 ms for EEG) of their capture time.",
    ),
    (
        "H7",
        "Ctrl+C mid-recording leaves a readable session",
        "SC-005: 100% of sessions interrupted by Ctrl+C or device loss reload without error.",
    ),
    (
        "H5",
        "Power-cycle recovery",
        "SC-003: After a 10-second headband power cycle, streaming resumes automatically "
        "within 20 seconds and the gap is recorded with duration accurate to ±0.5 s.",
    ),
    ("F1", "fNIRS optics: which channels are ambient light", "-"),
    (
        "H4",
        "10-minute recording completeness",
        "SC-002: A 10-minute recording has < 0.5% missing samples on every stream when the "
        "headband is within 2 m.",
    ),
    (
        "H3",
        "Time to first signal, 10 connects in a row",
        "SC-001: From headband power-on to live signal on screen in ≤ 15 seconds in ≥ 9 of 10 "
        "attempts.",
    ),
    ("H1/H2", "Discovery and 30 s of every stream", "-"),
)
ORDER = tuple(check for check, _, _ in _CHECKS)

Row = Mapping[str, Any]  # one line of acceptance.jsonl
Numbers = Mapping[str, float]

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,39}")  # a version, a preset, a commit
_OS = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+ -]{0,39}")
_AT = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}):\d{2}")
_DEVICE = re.compile(r"(Muse[A-Za-z0-9]*)-.+")
_CHANNELS = ("TP9", "AF7", "AF8", "TP10")
_STREAMS = {"eeg": "EEG", "motion": "motion", "optics": "optics"}  # manifest name: shown as


def mask_device(name: object) -> str | None:
    """`MuseS-1A2B` as `MuseS-****`: the family stays, what tells one headband from the next
    goes. Anything that is not a Muse name is not kept at all."""
    found = _DEVICE.fullmatch(name) if isinstance(name, str) else None
    return f"{found[1]}-****" if found else None


def _number(value: object) -> float | None:
    """`value` when it is a finite number; None for anything else a row may hold there."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        return None
    return float(value)


def _numbers(row: Row | None) -> dict[str, float]:
    """The row's measures that are numbers; anything else in there is dropped."""
    saved: object = row.get("measures") if row else None
    if not isinstance(saved, dict):
        return {}
    return {
        key: number
        for key, value in cast(dict[object, object], saved).items()
        if isinstance(key, str) and (number := _number(value)) is not None
    }


def _fact(rows: Sequence[Row], key: str, shape: re.Pattern[str] = _TOKEN) -> str | None:
    """The first value of `key` in `rows` that looks like what it should be."""
    for row in rows:
        value = row.get(key)
        if isinstance(value, str) and shape.fullmatch(value):
            return value
    return None


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(" --- " for _ in header) + "|"]
    return lines + ["| " + " | ".join(row) + " |" for row in rows]


# Key numbers ---------------------------------------------------------------------------------
# Per check, the numbers its judge decided on, each with its limit. A part whose number was not
# saved raises KeyError and is left out.


def _h6(m: Numbers) -> str:
    presses = (m.get(f"press_{i}.offset_s") for i in (1, 2, 3))
    found = ", ".join(
        f"{i}: {'none' if offset is None else f'{offset:+.1f} s'}"
        for i, offset in enumerate(presses, 1)
    )
    return (
        f"SPACE presses from their cues: {found} (window -{READY_S:.0f} to "
        f"+{PRESS_LATE_S:.0f} s); {m['presses']:.0f} SPACE markers saved"
    )


def _f1_rows(m: Numbers) -> str:
    rows = [n for n in range(1, 17) if m[f"ambient.OPT{n}"]]
    named = ", ".join(f"OPT{n}" for n in rows) if rows else "no row"
    wanted = f"OPT{AMBIENT_WIRE[0]} to OPT{AMBIENT_WIRE[-1]}"
    return f"rows that behaved as ambient light: {named} (expected {wanted}, BrainFlow wire order)"


def _f1_light(m: Numbers) -> str:
    rises = [
        min(m[f"room_light.OPT{n}.median"], m[f"light_again.OPT{n}.median"])
        - m[f"dark.OPT{n}.median"]
        for n in AMBIENT_WIRE
    ]
    return (
        f"room light added {min(rises):.0f} to {max(rises):.0f} counts over covered on those "
        f"four rows (need ≥ {LIGHT_RISE:.0f})"
    )


def _streams(m: Numbers) -> str:
    return ", ".join(
        f"{name} {m[f'{kind}.completeness_pct']:.2f}%" for kind, name in _STREAMS.items()
    )


_KEY: dict[str, tuple[Callable[[Numbers], str], ...]] = {
    "P0": (
        lambda m: f"battery {m['battery_pct']:.0f}% (need ≥ {BATTERY_MIN_PCT:.0f}%)",
        lambda m: f"{_streams(m)} of the nominal rate (need ≥ {STREAM_MIN_PCT:.0f}%)",
        lambda m: (
            "still windows the channel check called ok: "
            + ", ".join(f"{ch} {m[f'still.{ch}.ok_share']:.0%}" for ch in _CHANNELS)
            + f" (need ≥ {FIT_OK_SHARE:.0%})"
        ),
    ),
    "H8": (
        lambda m: (
            f"lifting the left ear sensor changed TP9 in {m['lift.TP9.changed_share']:.0%} of "
            f"windows (need ≥ 50%), against {m['rest.TP9.changed_share']:.0%} at rest (need < 50%)"
        ),
        lambda m: (
            f"jaw clench raised the std to {m['clench.TP9.std_ratio']:.1f} times rest on TP9 "
            f"and {m['clench.TP10.std_ratio']:.1f} times on TP10 (need ≥ {CHANGE_FACTOR:.0f} "
            "times on either)"
        ),
        lambda m: (
            f"blink-like deflections: AF7 {m['blink.AF7.deflections']:.0f}, AF8 "
            f"{m['blink.AF8.deflections']:.0f} (not judged)"
        ),
    ),
    "H6": (_h6,),
    "H7": (
        lambda m: f"{m['eeg_samples']:.0f} EEG samples saved",
        lambda m: (
            f"recording stopped {m['stopped_offset_s']:+.1f} s from the Ctrl+C cue (need within "
            f"{STOP_LATE_S:.0f} s)"
        ),
    ),
    "H5": (
        lambda m: f"gaps recorded: {m['gaps']:.0f}",
        lambda m: f"signal stopped {m['stopped_offset_s']:+.1f} s from the power-off cue",
        lambda m: f"signal away for {m['gap_s']:.1f} s (need ≥ {MIN_GAP_S:.0f} s)",
        lambda m: (
            f"streaming back {m['resume_s']:+.1f} s from the power-on cue (need ≤ "
            f"{RESUME_LIMIT_S:.0f} s after it, +{READY_S:.0f} s tolerance)"
        ),
        lambda m: (
            f"recorded gap {m['gap_s']:.2f} s against a hole of {m['hole_s']:.2f} s in the EEG "
            "data (need within ±0.5 s)"
        ),
    ),
    "F1": (_f1_rows, _f1_light),
    "H4": (
        lambda m: f"{_streams(m)} complete (need ≥ {COMPLETE_PCT:.2f}%)",
        lambda m: (
            "samples missing: "
            + ", ".join(
                f"{name} {m[f'{kind}.missing']:.0f} ({m[f'{kind}.lost_on_headset']:.0f} lost on "
                "the headset link)"
                for kind, name in _STREAMS.items()
            )
        ),
    ),
    "H3": (
        lambda m: (
            f"{m['h3.within_15_s']:.0f} of {m['h3.attempts']:.0f} connects reached EEG within "
            "15 s (need ≥ 9 of 10)"
        ),
        lambda m: f"slowest {m['h3.slowest_s']:.1f} s",
    ),
    "H1/H2": (lambda m: "the hardware tests' own verdict (`pytest -m hardware`)",),
}


def _key_numbers(check: str, m: Numbers) -> str:
    made: list[str] = []
    for part in _KEY[check]:
        try:
            made.append(part(m))
        except KeyError:
            continue
    return " · ".join(made) or "no numbers were saved"


# The report ----------------------------------------------------------------------------------


def render(rows: Sequence[Row], run: str) -> str:
    """The report of `run` from the ledger's rows. The last attempt or re-judgement of a check
    counts, as in the runner's own summary."""
    run_id = run if _TOKEN.fullmatch(run) else "unknown"
    own = [
        r
        for r in rows
        if r.get("run") == run and isinstance(r.get("at"), str) and _AT.fullmatch(r["at"])
    ]
    none: Row = {}
    start = next((r for r in own if r.get("kind") == "run"), none)
    judged = [
        r
        for r in own
        if r.get("kind") in ("attempt", "rejudge")
        and r.get("check") in ORDER
        and r.get("outcome") in (PASS, FAIL, SKIPPED, NOT_RUN)
    ]
    asked: object = start.get("checks")
    requested = [
        c
        for c in ORDER
        if (c in asked if isinstance(asked, list) else any(r["check"] == c for r in judged))
    ]
    last = {r["check"]: r for r in judged}  # where each check stands
    outcomes = {c: last[c]["outcome"] if c in last else NOT_RUN for c in requested}
    passed = sum(o == PASS for o in outcomes.values())
    rehearsal = any(r.get("source") != "athena" for r in own)
    short_h4 = _number(start.get("h4_seconds")) if rehearsal else None

    lines = [f"# MuFuse hardware acceptance, run {run_id}", ""]
    if rehearsal:
        lines.append(
            "> **SIMULATOR REHEARSAL: not hardware evidence.** Every number below comes from "
            "the simulator and its scripted wearer. It shows that the sitting runs from start "
            "to end; it says nothing about the headband."
        )
    else:
        lines.append(
            "One sitting with the Muse S Athena headband. This report is built from the "
            "numbers the checks saved: it holds no paths, names, addresses or samples."
        )
    result = f"{passed} of {len(outcomes)} requested checks passed"
    rest = [f"{n} {o}" for o in (FAIL, SKIPPED, NOT_RUN) if (n := list(outcomes.values()).count(o))]
    if rest:
        result += f": {', '.join(rest)}"
    lines += ["", *_facts(run_id, own, judged, rehearsal, result)]
    lines += ["", "## Checks", "", *_checks(run_id, judged, last, outcomes, short_h4)]
    lines += ["", "## Skipped and not run", "", *_left_out(last, outcomes)]
    lines += ["", "## Calibration", "", *_calibration(judged, last, rehearsal)]
    lines += ["", "## Reproduce", ""]
    lines += _reproduce(run_id, requested, rehearsal, short_h4, passed == len(outcomes))
    return "\n".join(lines) + "\n"


def _facts(
    run_id: str, own: Sequence[Row], judged: Sequence[Row], rehearsal: bool, result: str
) -> list[str]:
    missing = "not recorded"
    sitting = sorted(r["at"] for r in own if r.get("kind") != "rejudge")
    date = missing
    if sitting:
        (day, first), (last_day, last) = (
            cast(re.Match[str], _AT.fullmatch(at)).groups() for at in (sitting[0], sitting[-1])
        )
        date = (
            f"{day}, {first} to {last}"
            if day == last_day
            else f"{day} {first} to {last_day} {last}"
        )
    if rehearsal:
        source, headband = "simulator", "none: simulated"
    else:
        source = "Muse S Athena headband over BrainFlow"
        latest = judged[::-1]
        name = next((m for r in latest if (m := mask_device(r.get("device")))), None)
        headband = (
            f"{name or 'name ' + missing}, preset {_fact(latest, 'preset') or missing}, "
            f"firmware {_fact(latest, 'firmware') or missing}"
        )
    sat = [r for r in own if r.get("kind") != "rejudge"]  # a re-judgement names its own commit
    facts = [
        ("Date", date),
        ("Source", source),
        ("Headband", headband),
        ("Battery", _battery([r for r in judged if r["kind"] == "attempt"])),
        (
            "MuFuse",
            f"{_fact(sat, 'mufuse') or missing} at commit {_fact(sat, 'commit') or missing}",
        ),
        ("BrainFlow", _fact(sat, "brainflow") or missing),
        ("OS", _fact(sat, "os", _OS) or missing),
        ("Result", result),
    ]
    return _table(("Run", run_id), facts)


def _battery(attempts: Sequence[Row]) -> str:
    """The first and the last level the recordings saw, with the check each came from."""
    seen = [
        (r["check"], m.get("battery_pct", m.get("battery_end_pct")), m.get("battery_end_pct"))
        for r in attempts
        if (m := _numbers(r))
    ]
    first = next(((c, level) for c, level, _ in seen if level is not None), None)
    last = next(((c, level) for c, _, level in reversed(seen) if level is not None), None)
    if first is None or last is None:
        return "not reported"
    return f"{first[1]:.0f}% at the start ({first[0]}), {last[1]:.0f}% at the end ({last[0]})"


def _checks(
    run_id: str,
    judged: Sequence[Row],
    last: Mapping[str, Row],
    outcomes: Mapping[str, str],
    short_h4: float | None,
) -> list[str]:
    table: list[tuple[str, ...]] = []
    again: dict[tuple[str, str], list[str]] = {}  # (day, commit) -> checks judged again then
    for check, title, criterion in _CHECKS:
        if check not in outcomes:
            continue
        outcome, row = outcomes[check], last.get(check)
        recorded = [r for r in judged if r["check"] == check and r["kind"] == "attempt"]
        shown = outcome
        if row is not None and row["kind"] == "rejudge":
            before = recorded[-1]["outcome"] if recorded else None
            same = before in (None, outcome)
            shown += (
                " (judged again, same outcome)"
                if same
                else f" (judged again; {before} when recorded)"
            )
            day = cast(re.Match[str], _AT.fullmatch(row["at"]))[1]
            again.setdefault((day, _fact([row], "commit") or "not recorded"), []).append(check)
        tries = sum(r["outcome"] in (PASS, FAIL) for r in recorded)
        numbers = _key_numbers(check, _numbers(row)) if outcome in (PASS, FAIL) else "-"
        table.append((f"{check} · {title}", criterion, shown, str(tries), numbers))
    header = ("Check", "Success criterion", "Outcome", "Attempts", "Key numbers")
    lines = _table(header, table)
    notes = [
        f"Judged again from the saved sessions on {day} at commit {commit}: {', '.join(checks)}."
        for (day, commit), checks in again.items()
    ]
    if short_h4 is not None and "H4" in outcomes:
        notes.append(
            f"H4 was shortened to {short_h4:g} s for this rehearsal. On the headband it is ten "
            "minutes."
        )
    if FAIL in outcomes.values():
        short = "" if short_h4 is None else f" --h4-seconds {short_h4:g}"
        notes.append(
            "A failed check keeps its session on disk. This prints every rule with its numbers "
            f"from the saved sessions, without the headband: `{COMMAND}{short} --rejudge {run_id}`"
        )
    notes.append(
        "A check with no success criterion guards or informs the others: P0 is the preflight, "
        "H8 feeds the channel check of feature 002, F1 the optics of feature 004, and H1/H2 are "
        "the hardware tests. Attempts counts the recordings that were judged."
    )
    for note in notes:
        lines += ["", note]
    return lines


def _left_out(last: Mapping[str, Row], outcomes: Mapping[str, str]) -> list[str]:
    lines: list[str] = []
    for check, outcome in outcomes.items():
        if outcome in (PASS, FAIL):
            continue
        if check not in last:
            lines.append(f"- {check}: {NOT_RUN}. No result was recorded.")
            continue
        said: object = last[check].get("lines")
        why = cast(list[object], said)[0] if isinstance(said, list) and said else None
        if why in REASONS:
            end = "" if why.endswith("?") else "."
            lines.append(f"- {check}: {outcome}. Reason: {why}{end}")
        else:
            lines.append(f"- {check}: {outcome}. No reason was recorded.")
    if not lines:
        lines.append("Every requested check was run.")
    others = [c for c in ORDER if c not in outcomes]
    if others:
        lines += ["", f"Not requested in this run: {', '.join(others)}."]
    return lines


def _calibration(judged: Sequence[Row], last: Mapping[str, Row], rehearsal: bool) -> list[str]:
    # The numbers of a check's last judged recording, whatever came after it.
    rows = {r["check"]: r for r in judged if r["outcome"] in (PASS, FAIL)}
    measures = {check: _numbers(row) for check, row in rows.items()}
    tables = calibration.tables(measures)
    if not tables:
        return ["No calibration numbers were saved in this run."]
    lines = [
        "Numbers this run saved for tuning the live channel check (feature 002) and for the "
        "optics (feature 004). Suggestions only: nothing here changes `signal_check.py`. A "
        "change to it goes into a reviewed commit that cites this run and is checked with "
        "`--rejudge`.",
        "",
        "The robust spread is what the live channel check measures in each 2 s window: 1.4826 "
        "times the median distance from the median, which a short blink does not move. The "
        "plain std is the usual standard deviation of the same window.",
    ]
    if rehearsal:
        lines += [
            "",
            "These numbers come from the simulator's scripted wearer. Do not tune anything from "
            "them.",
        ]
    failed = [c for c in ("P0", "H8", "F1", "H4") if c in rows and last[c]["outcome"] != PASS]
    if failed:
        lines += [
            "",
            f"Not passed in this run: {', '.join(failed)}. Their rows may describe a phase that "
            "did not go as asked.",
        ]
    for table in tables:
        lines += ["", f"**{table.title}**", "", *_table(table.header, table.rows)]
        if table.note:
            lines += ["", table.note]
    lines += ["", "### Suggestions", ""]
    lines += [f"- {text}" for text in calibration.suggestions(measures)]
    return lines


def _reproduce(
    run_id: str, requested: Sequence[str], rehearsal: bool, short_h4: float | None, passed: bool
) -> list[str]:
    subset = "" if len(requested) in (0, len(ORDER)) else " " + " ".join(requested)
    if rehearsal:
        short = "" if short_h4 is None else f" --h4-seconds {short_h4:g}"
        return [
            f"- This rehearsal again, on the simulator: `{COMMAND} --rehearse{short}{subset}`",
            f"- The same checks on the headband: `{COMMAND}{subset}`",
        ]
    lines = [f"- The same checks in a new sitting: `{COMMAND}{subset}`"]
    if not passed:
        lines.append(f"- Only what this run has not passed: `{COMMAND} --resume {run_id}`")
    lines.append(
        "- Judge this run's saved sessions again, without the headband: "
        f"`{COMMAND} --rejudge {run_id}`"
    )
    lines.append(f"- Rehearse the sitting on the simulator: `{COMMAND} --rehearse`")
    return lines
