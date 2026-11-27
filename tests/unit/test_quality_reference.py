"""The rules against a stored reference session (FR-025, contracts/quality-rules.md section 9).

A change that alters any answer shows here. Then: run `scripts/make_quality_reference.py` and
raise `RULES_VERSION` in `src/mufuse/quality/rules.py` in the same commit.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from mufuse.quality.answer import to_json
from mufuse.quality.engine import judge
from mufuse.quality.rules import RULES_VERSION
from mufuse.recording.reader import load_session

REFERENCE = Path(__file__).parents[1] / "data" / "quality_reference"
TIME_S = 1e-9
BLINK_S = 1 / 256
VALUE_REL, VALUE_ABS = 1e-6, 1e-9


def _near(a: float | None, b: float | None, *, rel: float = 0.0, abs_: float = 0.0) -> bool:
    if a is None or b is None:
        return a is b
    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_)


def _compare(want: dict[str, Any], got: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if want["rules"] != got["rules"]:
        problems.append(f"rules {want['rules']} stored, {got['rules']} now")
    if len(want["answers"]) != len(got["answers"]):
        problems.append(f"{len(want['answers'])} answers stored, {len(got['answers'])} now")
    for i, (w, g) in enumerate(zip(want["answers"], got["answers"], strict=False)):
        where = f"answer {i} at {w['start']:.3f}"
        if not (
            _near(w["start"], g["start"], abs_=TIME_S) and _near(w["end"], g["end"], abs_=TIME_S)
        ):
            problems.append(f"{where}: times {g['start']}-{g['end']}")
        if w.get("no_data") != g.get("no_data"):
            problems.append(f"{where}: no_data differs")
            continue
        if w.get("no_data"):
            continue
        for key in ("eye", "tension", "movement", "coverage"):
            if w[key] != g[key]:
                problems.append(f"{where}: {key} {w[key]} stored, {g[key]} now")
        if not _near(w["tension_uv"], g["tension_uv"], rel=VALUE_REL, abs_=VALUE_ABS):
            problems.append(f"{where}: tension_uv {w['tension_uv']} stored, {g['tension_uv']} now")
        for sensor, wc in w["contact"].items():
            gc = g["contact"][sensor]
            if (wc["state"], wc["reason"]) != (gc["state"], gc["reason"]):
                problems.append(f"{where}: {sensor} {wc['state']}/{wc['reason']} stored, now {gc}")
            for value in ("spread_uv", "mains_share"):
                if not _near(wc[value], gc[value], rel=VALUE_REL, abs_=VALUE_ABS):
                    problems.append(
                        f"{where}: {sensor} {value} {wc[value]} stored, {gc[value]} now"
                    )
    if len(want["blinks"]) != len(got["blinks"]):
        problems.append(f"{len(want['blinks'])} blinks stored, {len(got['blinks'])} now")
    for w, g in zip(want["blinks"], got["blinks"], strict=False):
        if not _near(w["t"], g["t"], abs_=BLINK_S):
            problems.append(f"blink at {w['t']} stored, at {g['t']} now")
    for kind in ("tension_spans", "movement_spans"):
        ws, gs = want[kind], got[kind]
        same = len(ws) == len(gs) and all(
            _near(a["start"], b["start"], abs_=TIME_S) and _near(a["end"], b["end"], abs_=TIME_S)
            for a, b in zip(ws, gs, strict=True)
        )
        if not same:
            problems.append(f"{kind}: {ws} stored, {gs} now")
    return problems


def test_the_rules_give_the_stored_answers_for_the_reference_session() -> None:
    want = json.loads((REFERENCE / "answers.json").read_text(encoding="utf-8"))
    got = json.loads(json.dumps(to_json(judge(load_session(REFERENCE / "session")))))
    problems = _compare(want, got)
    assert not problems, (
        f"The quality rules (RULES_VERSION {RULES_VERSION}) no longer give the stored answers. "
        "If the change is meant, run `uv run python scripts/make_quality_reference.py` and raise "
        "RULES_VERSION in src/mufuse/quality/rules.py in the same commit.\n"
        + "\n".join(problems[:20])
    )


def test_the_reference_covers_every_fault_and_event() -> None:
    want = json.loads((REFERENCE / "answers.json").read_text(encoding="utf-8"))
    judged = [a for a in want["answers"] if not a.get("no_data")]
    reasons = {c["reason"] for a in judged for c in a["contact"].values()}
    assert {"floating", "loud", "flat", "railed"} <= reasons
    assert want["blinks"]
    assert want["tension_spans"]
    assert want["movement_spans"]


def test_a_changed_answer_is_named() -> None:
    want = json.loads((REFERENCE / "answers.json").read_text(encoding="utf-8"))
    got = json.loads(json.dumps(want))
    got["answers"][-1]["eye"] = "yes" if got["answers"][-1].get("eye") != "yes" else "no"
    got["blinks"] = got["blinks"][1:]
    problems = _compare(want, got)
    assert any("eye" in p for p in problems)
    assert any("blinks stored" in p for p in problems)
