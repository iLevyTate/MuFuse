from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mufuse.acceptance_report import COMMAND, REASONS, mask_device, render
from tests.unit.test_calibration import h8_numbers, phase_numbers

RUN = "20261126-100000"
GOLDEN = Path(__file__).parent / "golden" / "acceptance_report.md"
Row = dict[str, Any]

# What must never reach a report that is pasted into a public pull request.
USER = "alexdoe"
FOLDER = r"C:\Users\alexdoe\Documents\GitHub\MuFuse\recordings\20261126T100000Z-ab12"
MAC = "00:11:22:AB:CD:12"
DEVICE = "MuseS-9F3E"
SECRETS = (USER, "C:\\", "Users", MAC, "9F3E", "ab12", "a note about the day")


def _f1() -> dict[str, float]:
    m: dict[str, float] = {}
    for n in range(1, 17):
        ambient = 5 <= n <= 8
        m[f"on_head.OPT{n}.median"] = 338000.0 + n if ambient else 100000.0 + n
        m[f"room_light.OPT{n}.median"] = 341200.0 if ambient else 300.0
        m[f"dark.OPT{n}.median"] = 338000.0 if ambient else 60000.0
        m[f"light_again.OPT{n}.median"] = 341000.0 if ambient else 310.0
        m[f"on_head.OPT{n}.pulse_share"] = 0.01 if ambient else 0.4
        m[f"ambient.OPT{n}"] = float(ambient)
    return m


def _streams(pct: float) -> dict[str, float]:
    return {f"{kind}.completeness_pct": pct for kind in ("eeg", "motion", "optics")}


MEASURES: dict[str, dict[str, float]] = {
    "P0": {"battery_pct": 82.0, "battery_end_pct": 82.0}
    | _streams(99.9)
    | phase_numbers("still", (9.0, 14.0, 19.0)),
    "H8": h8_numbers()
    | {"lift.TP9.changed_share": 1.0, "rest.TP9.changed_share": 0.0}
    | {"clench.TP9.std_ratio": 5.04, "clench.TP10.std_ratio": 5.1}
    | {"blink.AF7.deflections": 9.0, "blink.AF8.deflections": 8.0, "battery_end_pct": 81.0},
    "H6": {"press_1.offset_s": 0.4, "press_3.offset_s": -0.2, "presses": 2.0},
    "H7": {"eeg_samples": 3969.0, "stopped_offset_s": 1.05, "battery_end_pct": 81.0},
    "H5": {"gaps": 1.0, "gap_s": 24.66, "resume_s": 25.3, "hole_s": 24.7},
    "F1": _f1() | {"battery_end_pct": 80.0},
    "H4": _streams(99.72)
    | {f"{k}.missing": 430.0 for k in ("eeg", "motion", "optics")}
    | {f"{k}.lost_on_headset": 400.0 for k in ("eeg", "motion", "optics")}
    | phase_numbers("whole", (8.0, 13.0, 30.0))
    | {"battery_end_pct": 77.0},
    "H3": {"h3.attempts": 10.0, "h3.within_15_s": 9.0, "h3.slowest_s": 16.2},
}


def _row(kind: str, at: str, source: str = "athena", **fields: Any) -> Row:
    versions = {"mufuse": "0.1.0", "brainflow": "5.24.0", "commit": "abc1234", "os": "Windows 11"}
    return (
        {"run": RUN, "at": f"2026-11-26T{at}", "kind": kind, "source": source} | versions | fields
    )


def _attempt(check: str, outcome: str, at: str, attempt: int = 1, **fields: Any) -> Row:
    judged = outcome in ("PASS", "FAIL") and check in MEASURES
    row = {
        "check": check,
        "attempt": attempt,
        "outcome": outcome,
        "lines": [f"[ok] saved to {FOLDER}", f"[info] headband {DEVICE} at {MAC}"],
        "measures": MEASURES[check] if judged else {},
        "firmware": "3.1.19" if judged else None,
        "preset": "p1041" if judged else None,
        "device": DEVICE if judged else None,  # a row written before names were masked
        "session": FOLDER if judged else None,
        "address": MAC,
        "notes": "a note about the day",
        "user": USER,
    }
    return _row("attempt", at, **(row | fields))


def _run(source: str = "athena") -> list[Row]:
    """A whole sitting: H8 passes on its second attempt, H5 fails, H6 is skipped."""
    checks = ["P0", "H8", "H6", "H7", "H5", "F1", "H4", "H3", "H1/H2"]
    skipped = ["skipped at the keyboard"]
    rows = [
        _row("run", "10:00:00", checks=checks),
        _attempt("P0", "PASS", "10:01:10"),
        _attempt("H8", "FAIL", "10:02:40", measures={}),
        _attempt("H8", "PASS", "10:04:30", attempt=2),
        _attempt("H6", "SKIPPED", "10:04:40", lines=skipped),
        _attempt("H7", "PASS", "10:06:00"),
        _attempt("H5", "FAIL", "10:07:40"),
        _attempt("F1", "PASS", "10:09:50"),
        _attempt("H4", "PASS", "10:20:10"),
        _attempt("H3", "PASS", "10:25:30"),
        _attempt("H1/H2", "PASS", "10:26:40"),
        _row("summary", "10:26:40", outcomes={}, passed=False),
    ]
    return [r | {"source": source} for r in rows]


def test_the_report_of_a_whole_run_reads_like_this() -> None:
    assert render(_run(), RUN) == GOLDEN.read_text(encoding="utf-8")


def test_nothing_personal_planted_in_the_rows_reaches_the_report() -> None:
    rows = _run()
    rows[0] |= {"out": FOLDER, "device": DEVICE}

    text = render(rows, RUN)

    for secret in SECRETS:
        assert secret not in text, secret
    assert "MuseS-****" in text


@pytest.mark.parametrize("field", ["firmware", "preset", "commit", "mufuse", "brainflow", "os"])
def test_a_fact_that_is_not_a_plain_token_is_left_out(field: str) -> None:
    rows = [r | {field: FOLDER} for r in _run()]

    text = render(rows, RUN)

    for secret in SECRETS:
        assert secret not in text, secret


def test_measures_are_read_by_name_and_only_as_numbers() -> None:
    rows = _run()
    planted = {"battery_pct": FOLDER, MAC: 1.0, "still.TP9.spread_uv": DEVICE}
    rows[1]["measures"] = rows[1]["measures"] | planted

    text = render(rows, RUN)

    for secret in SECRETS:
        assert secret not in text, secret


def test_the_device_name_is_masked_down_to_its_family() -> None:
    assert mask_device(DEVICE) == "MuseS-****"
    assert mask_device("MuseS-****") == "MuseS-****"
    assert mask_device("Muse-2-AB12") == "Muse-****"
    assert mask_device("SimulatedAthena") is None
    assert mask_device(r"C:\Users\alexdoe") is None
    assert mask_device(None) is None


def test_a_rehearsal_says_first_that_it_is_not_hardware_evidence() -> None:
    lines = render(_run("sim"), RUN).splitlines()

    assert lines[0].startswith("# MuFuse hardware acceptance")
    assert "SIMULATOR REHEARSAL" in lines[2]
    assert "not hardware evidence" in lines[2]
    text = "\n".join(lines)
    assert "MuseS" not in text
    assert f"{COMMAND} --rehearse" in text
    assert "Do not tune anything from them" in text
    assert "SIMULATOR REHEARSAL" not in render(_run(), RUN)


def test_one_simulated_row_is_enough_to_mark_the_whole_report() -> None:
    rows = _run()
    rows[4]["source"] = "sim"

    assert "SIMULATOR REHEARSAL" in render(rows, RUN)


def test_a_rehearsal_with_a_short_h4_gives_the_command_that_made_it() -> None:
    rows = _run("sim")
    rows[0]["h4_seconds"] = 30.0

    text = render(rows, RUN)

    assert f"{COMMAND} --rehearse --h4-seconds 30" in text
    assert f"{COMMAND} --h4-seconds 30 --rejudge {RUN}" in text  # H5 failed in this run
    assert "H4 was shortened to 30 s for this rehearsal" in text


def test_a_subset_names_what_was_not_requested_and_how_to_run_it_again() -> None:
    rows = [r for r in _run() if r.get("check") in (None, "H5", "F1")]
    rows[0]["checks"] = ["H5", "F1"]

    text = render(rows, RUN)

    assert "1 of 2 requested checks passed" in text
    assert "Not requested in this run: P0, H8, H6, H7, H4, H3, H1/H2." in text
    assert f"{COMMAND} H5 F1" in text
    assert "| P0 " not in text


def test_skipped_and_not_run_checks_are_listed_with_a_known_reason_only() -> None:
    rows = _run()[:8]  # the run died after F1: no rows for H4, H3 and H1/H2
    rows[6] = _attempt("H5", "NOT RUN", "10:07:40", lines=[f"the user {USER} went for lunch"])

    text = render(rows, RUN)

    assert "- H6: SKIPPED. Reason: skipped at the keyboard." in text
    assert "- H5: NOT RUN. No reason was recorded." in text
    assert "- H4: NOT RUN. No result was recorded." in text
    assert USER not in text
    assert "skipped at the keyboard" in REASONS


def test_a_check_judged_again_shows_both_outcomes_and_who_judged() -> None:
    again = _attempt("H5", "PASS", "09:15:00", commit="def5678") | {
        "kind": "rejudge",
        "at": "2026-11-27T09:15:00",
    }
    rows = [*_run(), again]

    text = render(rows, RUN)

    assert "| PASS (judged again; FAIL when recorded) | 1 |" in text
    assert "9 of 9" not in text  # H6 is still skipped
    assert "8 of 9 requested checks passed" in text
    assert "Judged again from the saved sessions on 2026-11-27 at commit def5678: H5." in text
    assert "| Date | 2026-11-26, 10:00 to 10:26 |" in text  # the sitting, not the re-judgement


def test_a_passed_run_does_not_offer_to_resume() -> None:
    rows = [r for r in _run() if r.get("check") in (None, "P0")]
    rows[0]["checks"] = ["P0"]

    text = render(rows, RUN)

    assert "| Result | 1 of 1 requested checks passed |" in text
    assert "--resume" not in text


def test_the_result_says_how_the_other_checks_ended() -> None:
    rows = _run()[:8]  # H6 skipped, H5 failed, and no rows for H4, H3 and H1/H2

    text = render(rows, RUN)

    assert "| Result | 4 of 9 requested checks passed: 1 FAIL, 1 SKIPPED, 3 NOT RUN |" in text


def test_the_calibration_says_what_its_two_measures_are() -> None:
    text = render(_run(), RUN)

    assert "The robust spread is what the live channel check measures" in text
    assert "1.4826 times the median distance from the median" in text
    assert "--resume" in render(_run(), RUN)


def test_rows_of_other_runs_and_torn_rows_are_ignored() -> None:
    other = [r | {"run": "20261125-090000", "firmware": "9.9.9"} for r in _run()]
    torn: list[Row] = [{"run": RUN}, {"run": RUN, "kind": "attempt", "check": "H9", "at": 3}]

    assert render([*other, *_run(), *torn], RUN) == render(_run(), RUN)


def test_a_run_with_no_rows_still_renders() -> None:
    text = render([], RUN)

    assert f"run {RUN}" in text
    assert "0 of 0" in text
