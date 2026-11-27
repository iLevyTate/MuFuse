"""Every hardware acceptance check, rehearsed in-process without the headband.

A scripted wearer follows each check's cues, or ignores them, while the real record loop,
supervisor, writer and judge run on a fake clock. A green rehearsal proves the pipeline, not the
physiology: what a lifted sensor, a clench or room light look like here is modelled on one
public capture and on guesses (see `mufuse.acquisition.simulated`).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from mufuse.acceptance import CHECKS, Check, Result, wearer_for
from mufuse.acquisition.simulated import Rehearsal, Wearer
from mufuse.cli import (
    SourceKind,
    _Attempt,  # pyright: ignore[reportPrivateUsage]
    _run,  # pyright: ignore[reportPrivateUsage]
)
from mufuse.recording.reader import LoadedSession, load_session
from mufuse.recording.writer import SessionWriter
from tests.conftest import FakeClock

# The loop turns every 0.25 s in here, not every 0.05 s: the same code on a fifth of the turns,
# which keeps the whole file under 3 s. Connect, scan and release times pass in full.
TICK_S = 0.25
H4_SHORT = replace(CHECKS["H4"], duration=30.0)  # ten minutes prove nothing more in here
REHEARSED = [*(c for c in CHECKS.values() if c.id != "H4"), H4_SHORT]
HANDS_ON = {  # what the judge says to a wearer who did nothing
    "H8": "lifting the left ear sensor changed TP9 in 0% of windows",
    "H6": "press 1: none in its window",
    "H7": "from the Ctrl+C cue",
    "H5": "no interruption was seen at all",
    "F1": "face a lamp or a window",
}


def _rehearse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clock: FakeClock,
    check: Check,
    wearer: Wearer,
) -> tuple[Result, LoadedSession]:
    """One check the way the launcher runs it: its guide, one recording, then the judge."""
    guide_file = tmp_path / "guide.json"
    check.guide().save(guide_file)
    monkeypatch.setenv("MUFUSE_GUIDE", str(guide_file))
    rehearsal = Rehearsal(wearer, clock=clock, sleep=clock.advance)
    out = tmp_path / "sessions"
    _run(
        _Attempt("record", SourceKind.sim, "p1041", clock.now),
        rehearsal.source,
        check.duration,
        lambda src: SessionWriter.create(out, src.device, src.streams, clock=clock),
        clock=clock,
        sleep=lambda _: clock.advance(TICK_S),
        read_key=rehearsal.read_key,
    )
    (session_dir,) = out.iterdir()
    session = load_session(session_dir)
    return check.evaluate(session), session


def _report(result: Result) -> str:
    return "\n".join(result.lines)


@pytest.mark.parametrize("check", REHEARSED, ids=lambda c: c.id)
def test_a_wearer_who_follows_the_cues_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: FakeClock, check: Check
) -> None:
    result, _ = _rehearse(tmp_path, monkeypatch, clock, check, wearer_for(check))
    assert result.passed, _report(result)


@pytest.mark.parametrize("check_id", list(HANDS_ON))
def test_a_wearer_who_does_nothing_fails_a_hands_on_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: FakeClock, check_id: str
) -> None:
    check = CHECKS[check_id]
    result, _ = _rehearse(tmp_path, monkeypatch, clock, check, wearer_for(check, idle=True))
    assert not result.passed, _report(result)
    assert any(line.startswith("[FAIL]") and HANDS_ON[check_id] in line for line in result.lines)


def test_h7_passes_with_a_late_ctrl_c_and_a_slow_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    wearer = replace(wearer_for(CHECKS["H7"], react=3.0), stop_s=7.0)
    result, session = _rehearse(tmp_path, monkeypatch, clock, CHECKS["H7"], wearer)
    assert result.passed, _report(result)
    assert result.measures["stopped_offset_s"] == pytest.approx(3.0, abs=2 * TICK_S)
    assert clock.now - session.manifest["ended_at"] >= 7.0  # saved first, released after


def test_h5_passes_with_the_scan_and_connect_times_of_a_real_headband(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    # The slowest connect measured so far (5.8 s to the first sample) and a full failed scan.
    wearer = replace(wearer_for(CHECKS["H5"]), scan_s=16.0, connect_s=5.3, first_data_s=0.5)
    result, session = _rehearse(tmp_path, monkeypatch, clock, CHECKS["H5"], wearer)
    assert result.passed, _report(result)
    assert len(session.gaps) == 1
    assert 16.0 < result.measures["resume_s"] < 20.0  # one scan in vain, then the connect


def test_h6_passes_with_a_double_tap_and_a_key_typed_ahead(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    following = wearer_for(CHECKS["H6"])
    (first, _), *_ = following.keys
    wearer = replace(following, keys=((-2.0, " "), *following.keys, (first + 0.2, " ")))
    result, _ = _rehearse(tmp_path, monkeypatch, clock, CHECKS["H6"], wearer)
    assert result.passed, _report(result)
    assert result.measures["presses"] == 4  # the one typed while connecting is not this run's
    assert any("4 SPACE markers, 1 extra" in line for line in result.lines)
