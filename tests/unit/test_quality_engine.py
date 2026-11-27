"""The combined answer per stretch (contracts/quality-rules.md, sections 3, 7 and 8)."""

from __future__ import annotations

import ast
import json
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import numpy as np

from mufuse.acquisition.simulated import Wearer
from mufuse.acquisition.types import Chunk, FloatArray, StreamKind
from mufuse.quality.answer import (
    SENSORS,
    Blink,
    ContactState,
    Coverage,
    QualityAnswer,
    SessionQuality,
    Span,
    spans,
    to_json,
)
from mufuse.quality.engine import QualityEngine
from mufuse.quality.rules import RULES_VERSION
from mufuse.quality.tension import tension_level
from tests.conftest import QUICK, FakeClock, eeg_chunk, motion_chunk, rehearse

FS = 256
RNG = np.random.default_rng(33)


def _judge(chunks: Sequence[Chunk]) -> tuple[tuple[QualityAnswer, ...], tuple[Blink, ...]]:
    engine = QualityEngine()
    fed, done = engine.feed(chunks), engine.finish()
    return fed.answers + done.answers, fed.blinks + done.blinks


def _rehearsed(
    wearer: Wearer, clock: FakeClock, seconds: float
) -> tuple[tuple[QualityAnswer, ...], tuple[Blink, ...], float]:
    """Answers and blinks of a scripted wearer, read by read as live, and the first timestamp."""
    reads = rehearse(wearer, clock, seconds)
    first = next(c.timestamps[0] for read in reads for c in read if c.kind is StreamKind.EEG)
    engine, answers, blinks = QualityEngine(), [], []
    for read in reads:
        judged = engine.feed(read)
        answers += judged.answers
        blinks += judged.blinks
    judged = engine.finish()
    return (*answers, *judged.answers), (*blinks, *judged.blinks), float(first)


# 3 Forehead sensors in use ----------------------------------------------------------------


def _forehead_session(seconds: int) -> FloatArray:
    n = seconds * FS
    t = np.arange(n) / FS
    eeg = 10.0 * RNG.standard_normal((n, 4))
    eeg[:, 1:3] += -54.0 + 20.0 * np.sin(2 * np.pi * 10 * t)[:, None]
    return eeg


def test_a_forehead_sensor_without_contact_is_not_read() -> None:
    eeg = _forehead_session(8)
    t = np.arange(len(eeg)) / FS
    eeg[:, 1] = 300.0 * np.sin(2 * np.pi * 60 * t) + 5.0 * RNG.standard_normal(len(eeg))  # AF7 off
    eeg[3 * FS : 5 * FS, 2] += 30.0 * RNG.standard_normal(2 * FS)  # a clench on AF8
    answers, _ = _judge([eeg_chunk(eeg, 100.0), motion_chunk(np.zeros((8 * 52, 6)), 100.0)])
    for i, answer in enumerate(answers):
        assert answer.state("AF7").state == "none"
        assert answer.tension_uv == tension_level(eeg[i * FS : (i + 1) * FS, 2])
    assert [a.tension for a in answers] == ["no", "no", "no", "yes", "yes", "no", "no", "no"]


def test_without_a_forehead_sensor_eye_and_tension_are_unavailable() -> None:
    eeg = _forehead_session(8)
    t = np.arange(len(eeg)) / FS
    eeg[:, 1:3] = 300.0 * np.sin(2 * np.pi * 60 * t)[:, None]
    answers, blinks = _judge([eeg_chunk(eeg, 100.0), motion_chunk(np.zeros((8 * 52, 6)), 100.0)])
    for answer in answers:
        assert (answer.eye, answer.tension, answer.tension_uv) == (
            "unavailable",
            "unavailable",
            None,
        )
        assert answer.movement == "still"  # the motion sensors do not need skin contact
    assert blinks == ()


# 7 Spans ----------------------------------------------------------------------------------

GOOD = tuple(ContactState(name, "good", None, 14.0, 0.1) for name in SENSORS)


def _answer(second: int, tension: str = "no", movement: str = "still") -> QualityAnswer:
    return QualityAnswer(
        start=100.0 + second,
        end=101.0 + second,
        rules=RULES_VERSION,
        contact=GOOD,
        coverage=Coverage("full", ()),
        eye="no",
        tension=tension,  # type: ignore[arg-type]
        tension_uv=4.8,
        movement=movement,  # type: ignore[arg-type]
    )


def test_marked_stretches_in_a_row_are_one_span_and_a_gap_ends_a_span() -> None:
    marks = ["no", "yes", "yes", "no", "yes"]
    row = [_answer(i, tension=m) for i, m in enumerate(marks)]
    row += [QualityAnswer.gap(105.0, 107.5)]
    row += [_answer(i + 2, tension="yes") for i in range(5, 8)]  # 107.5 is the next start
    row[-3] = replace(row[-3], start=107.5, end=108.5)
    row[-2] = replace(row[-2], start=108.5, end=109.5)
    row[-1] = replace(row[-1], start=109.5, end=110.5)
    assert spans(row, "tension") == (
        Span("tension", 101.0, 103.0),
        Span("tension", 104.0, 105.0),
        Span("tension", 107.5, 110.5),
    )
    assert spans(row, "movement") == ()


def test_long_tension_is_one_span_and_movement_has_its_own() -> None:
    row = [
        _answer(i, tension="yes", movement="moving" if i in (3, 4) else "still") for i in range(30)
    ]
    assert spans(row, "tension") == (Span("tension", 100.0, 130.0),)
    assert spans(row, "movement") == (Span("movement", 103.0, 105.0),)
    assert spans([], "tension") == ()


# 8 Clean ----------------------------------------------------------------------------------


def test_a_quiet_stretch_is_clean_and_several_reasons_show_together(clock: FakeClock) -> None:
    wearer = replace(
        QUICK,
        blinks=((12.0, 12.5),),
        clench=((12.0, 13.0),),
        turns=((12.0, 14.0),),
        lifted=((0.0, 60.0, "TP9"),),
    )
    answers, _, _ = _rehearsed(wearer, clock, 20.0)
    quiet, busy = answers[8], answers[12]
    for sensor in ("AF7", "AF8"):
        assert quiet.clean(sensor), quiet.reasons(sensor)
        assert busy.reasons(sensor) == ("eye", "tension", "movement")
    assert quiet.clean("TP10")
    assert busy.reasons("TP10")[-3:] == ("eye", "tension", "movement")  # a clench is loud there
    assert quiet.reasons("TP9") == ("none:floating",)
    assert busy.reasons("TP9")[-3:] == ("eye", "tension", "movement")


def test_no_blink_is_reported_from_an_unavailable_stretch(clock: FakeClock) -> None:
    answers, blinks, first = _rehearsed(
        replace(QUICK, blinks=((2.0, 2.5), (8.0, 8.5))), clock, 12.0
    )
    assert answers[2].eye == "unavailable"
    assert [round(b.t - first) for b in blinks] == [8]


# The independent test of user story 2 -----------------------------------------------------

BLINKS = [10.0 + 4 * k for k in range(20)]  # 10 ... 86
CLENCHES = [95.0 + 5 * k for k in range(20)]  # 95 ... 190, about 1 s each
TURNS = [200.0 + 5 * k for k in range(20)]  # 200 ... 295, 2 s each
REACT_S = 0.4


def test_twenty_scripted_blinks_clenches_and_turns(clock: FakeClock) -> None:
    wearer = replace(
        QUICK,
        blinks=tuple((c + REACT_S, c + REACT_S + 0.5) for c in BLINKS),
        clench=tuple((c + REACT_S, c + REACT_S + 1.0) for c in CLENCHES),
        turns=tuple((c + REACT_S, c + REACT_S + 2.0) for c in TURNS),
    )
    answers, blinks, first = _rehearsed(wearer, clock, 330.0)
    times = [b.t - first for b in blinks]
    starts = {
        kind: [s.start - first for s in spans(answers, kind)] for kind in ("tension", "movement")
    }

    def stretch_start(cue: float) -> float:
        return max(a.start - first for a in answers if a.start - first <= cue + 1e-9)

    found = {
        "blinks": sum(any(c <= t <= c + 2.0 for t in times) for c in BLINKS),
        "clenches": sum(
            any(stretch_start(c) <= s <= c + 2.0 for s in starts["tension"]) for c in CLENCHES
        ),
        "turns": sum(
            any(stretch_start(c) <= s <= c + 2.0 for s in starts["movement"]) for c in TURNS
        ),
    }
    assert min(found.values()) >= 18, found
    assert len(times) <= 22  # no blinks where there were none
    quiet = [a for a in answers if a.start - first >= 305.0 and a.end - first <= 329.0]
    assert len(quiet) >= 20
    assert {(a.eye, a.tension, a.movement) for a in quiet} == {("no", "no", "still")}


# The guarantees of contracts/quality-interface.md -------------------------------------------

QUALITY_SRC = Path(__file__).parents[2] / "src" / "mufuse" / "quality"
MAY_TOUCH_FILES = {"labelled.py", "public_set.py"}  # they read markers and the public set
NOT_HERE = ("time", "datetime", "socket", "ssl", "urllib", "http", "requests", "subprocess",
            "os", "io", "pathlib", "shutil", "tempfile",
            "mufuse.recording", "mufuse.runlog")  # fmt: skip


def _imports(tree: ast.Module) -> list[tuple[str, int]]:
    """Modules imported at run time (imports only for type checking are left out)."""
    found: list[tuple[str, int]] = []
    skip: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and "TYPE_CHECKING" in ast.unparse(node.test):
            skip |= {id(n) for n in ast.walk(node)}
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.Import):
            found += [(a.name, node.lineno) for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append((node.module, node.lineno))
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ("open", "input", "print")
        ):
            found.append((f"{node.func.id}()", node.lineno))
    return found


def test_the_engine_has_no_clock_no_network_and_no_file() -> None:
    checked = 0
    for path in sorted(QUALITY_SRC.glob("*.py")):
        if path.name in MAY_TOUCH_FILES:
            continue
        checked += 1
        for name, line in _imports(ast.parse(path.read_text(encoding="utf-8"))):
            bad = name.endswith("()") or any(
                name == m or name.startswith(f"{m}.") for m in NOT_HERE
            )
            assert not bad, f"{path.name}:{line} uses {name}"
    assert checked >= 8


def test_every_answer_names_its_rules_and_is_given_once(clock: FakeClock) -> None:
    answers, _, _ = _rehearsed(replace(QUICK, off=()), clock, 12.0)
    assert {a.rules for a in answers} == {RULES_VERSION}
    starts = [a.start for a in answers]
    assert starts == sorted(set(starts))  # each stretch once, in time order, never revised


def test_to_json_holds_every_field(clock: FakeClock) -> None:
    wearer = replace(QUICK, blinks=((8.0, 9.0),), clench=((9.0, 10.0),), turns=((10.0, 11.0),))
    answers, blinks, _ = _rehearsed(wearer, clock, 14.0)
    gap = QualityAnswer.gap(answers[-1].end, answers[-1].end + 2.5)
    quality = SessionQuality.of((*answers, gap), blinks)
    data = json.loads(json.dumps(to_json(quality)))
    assert data["rules"] == RULES_VERSION
    first = data["answers"][0]
    assert set(first) == {
        "start", "end", "contact", "coverage", "eye", "tension", "tension_uv", "movement"
    }  # fmt: skip
    assert set(first["contact"]) == set(SENSORS)
    assert set(first["contact"]["AF7"]) == {"state", "reason", "spread_uv", "mains_share"}
    assert set(first["coverage"]) == {"level", "out"}
    assert data["answers"][-1] == {"start": gap.start, "end": gap.end, "no_data": True}
    assert data["blinks"] == [{"t": b.t, "duration_s": b.duration_s} for b in blinks]
    assert data["tension_spans"] == [
        {"start": s.start, "end": s.end} for s in quality.tension_spans
    ]
    assert data["movement_spans"] == [
        {"start": s.start, "end": s.end} for s in quality.movement_spans
    ]
    assert data["answers"][9]["tension"] == "yes"
