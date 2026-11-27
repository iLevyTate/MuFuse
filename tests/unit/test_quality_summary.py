"""The quality summary of a session (data-model.md, QualitySummary)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.simulated import Wearer
from mufuse.acquisition.types import DeviceInfo
from mufuse.quality.answer import (
    SENSORS,
    Blink,
    ContactState,
    Coverage,
    QualityAnswer,
    SessionQuality,
)
from mufuse.quality.engine import judge
from mufuse.quality.rules import RULES_VERSION
from mufuse.quality.summary import summarize, summary_lines
from mufuse.recording.reader import load_session
from mufuse.recording.writer import SessionWriter
from tests.conftest import QUICK, FakeClock, rehearse


def _answer(
    second: float,
    *,
    tp9: str = "good",
    eye: str = "no",
    tension: str = "no",
    movement: str = "still",
    coverage: str = "full",
) -> QualityAnswer:
    reason = {"good": None, "settling": None, "noisy": "loud", "none": "hum"}[tp9]
    contact = tuple(
        ContactState(n, tp9 if n == "TP9" else "good", reason if n == "TP9" else None, 10.0, 0.1)  # type: ignore[arg-type]
        for n in SENSORS
    )
    return QualityAnswer(
        start=100.0 + second,
        end=101.0 + second,
        rules=RULES_VERSION,
        contact=contact,
        coverage=Coverage(coverage, () if coverage == "full" else ("TP9",)),  # type: ignore[arg-type]
        eye=eye,  # type: ignore[arg-type]
        tension=tension,  # type: ignore[arg-type]
        tension_uv=None if tension == "unavailable" else 4.0,
        movement=movement,  # type: ignore[arg-type]
    )


def test_shares_are_over_judged_time_and_a_gap_is_left_out() -> None:
    answers = (
        _answer(0, tp9="none", coverage="reduced"),
        _answer(1, tp9="none", coverage="reduced"),
        _answer(2, tp9="noisy", coverage="reduced", eye="yes"),
        _answer(3),
        QualityAnswer.gap(104.0, 110.0),
        _answer(10, tp9="settling", coverage="reduced", tension="yes", movement="moving"),
    )
    s = summarize(SessionQuality.of(answers, ()))
    assert (s.rules, s.judged_s, s.no_data_s) == (RULES_VERSION, 5.0, 6.0)
    tp9, af7 = s.sensors["TP9"], s.sensors["AF7"]
    assert (tp9.good, tp9.settling, tp9.noisy, tp9.none) == (0.2, 0.2, 0.2, 0.4)
    assert tp9.clean == 0.2
    assert (af7.good, af7.clean) == (1.0, 0.6)  # the eye mark and the tension stretch are not clean
    assert s.coverage == {"full": 0.2, "reduced": 0.8, "one_forehead": 0.0, "none": 0.0}
    assert (s.tension_share, s.movement_share, s.movement_unknown_s) == (0.2, 0.2, 0.0)


def test_nothing_to_divide_by_is_not_available_never_zero() -> None:
    s = summarize(SessionQuality.of((QualityAnswer.gap(100.0, 103.0),), ()))
    assert (s.judged_s, s.no_data_s) == (0.0, 3.0)
    assert s.sensors["AF7"].good is None
    assert s.coverage["full"] is None
    assert (s.blinks, s.blinks_per_min, s.tension_share, s.movement_share) == (None,) * 4
    assert s.blink_available_s == 0.0
    text = "\n".join(summary_lines(s))
    assert "not available" in text
    assert " 0%" not in text


def test_blinks_per_minute_are_over_the_time_the_mark_was_available() -> None:
    answers = tuple(
        _answer(i, eye="unavailable" if i < 60 else "no", movement="unknown" if i < 5 else "still")
        for i in range(120)
    )
    blinks = tuple(Blink(170.0 + 4 * k, 0.3) for k in range(10))
    s = summarize(SessionQuality.of(answers, blinks))
    assert (s.blinks, s.blink_available_s, s.blinks_per_min) == (10, 60.0, 10.0)
    assert s.movement_unknown_s == 5.0


def test_the_summary_reads_like_the_contract() -> None:
    answers = tuple(_answer(i, tp9="none", coverage="reduced") for i in range(60))
    s = summarize(SessionQuality.of(answers, (Blink(130.0, 0.3),)))
    lines = summary_lines(s)
    assert lines[0] == f"Signal quality (rules {RULES_VERSION})"
    assert lines[1] == "  judged 1:00 · no data 0:00"
    assert lines[2] == "  sensor   good  settling  noisy  no contact  clean"
    assert lines[3] == "  TP9        0%        0%     0%        100%     0%"
    assert lines[4] == "  AF7      100%        0%     0%          0%   100%"
    assert lines[7] == "  coverage  full 0% · reduced 100% · one forehead sensor 0% · none 0%"
    assert lines[8] == "  blinks    1 (1.0 per minute over 1:00)"
    assert lines[9] == "  marked    muscle activity 0% · head movement 0% · movement unknown 0:00"


def test_a_scripted_session_gives_the_shares_of_its_script(
    tmp_path: Path, clock: FakeClock
) -> None:
    wearer: Wearer = replace(
        QUICK,
        lifted=((0.0, 999.0, "TP9"),),
        blinks=((10.0, 15.0),),  # five blinks, once a second
        turns=((20.0, 22.0),),
    )
    writer = SessionWriter.create(
        tmp_path, DeviceInfo("SimulatedAthena", "p1041", "simulated"), ATHENA_STREAMS, clock=clock
    )
    for read in rehearse(wearer, clock, 30.0):
        writer.write(read)
    writer.finalize()
    s = summarize(judge(load_session(writer.session_dir)))
    assert s.judged_s == pytest.approx(29.0, abs=1.0)
    assert s.no_data_s == 0.0
    assert s.sensors["TP9"].none == 1.0
    assert s.sensors["AF7"].good == pytest.approx((s.judged_s - 2.0) / s.judged_s)
    assert s.blinks == 5
    assert s.movement_share == pytest.approx(2.0 / s.judged_s)
    assert s.tension_share == 0.0
