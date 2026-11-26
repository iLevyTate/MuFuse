"""The one-sitting runner: order, countdowns, stops, retries, evidence rows, resume, re-judge."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from mufuse.acceptance import CHECKS, Check
from mufuse.acceptance_report import ORDER, REASONS
from mufuse.acquisition.types import StreamKind
from mufuse.cli import EXIT_CONNECT, EXIT_WRITE
from mufuse.recording.reader import LoadedSession
from mufuse.runlog import ConnectRun, append_run
from mufuse.sitting import (
    COOLDOWN_S,
    ENDED,
    FAIL,
    NOT_RUN,
    PASS,
    RELEASE_S,
    SKIPPED,
    STEPS,
    Launcher,
    Ran,
    Sitting,
    SittingError,
    Step,
    Verdict,
    _ask,  # pyright: ignore[reportPrivateUsage]
    _selection_off,  # pyright: ignore[reportPrivateUsage]
    _spawn,  # pyright: ignore[reportPrivateUsage]
    judged,
    last_release,
    main,
    new_session,
    plan,
    read_rows,
    rejudge,
    settled,
    standing,
    to_resume,
    versions,
    write_report,
)
from tests.conftest import FakeClock

RUN = "20261126-100000"
VERSIONS: dict[str, str | None] = {"mufuse": "0.1.0", "brainflow": "5.24.0", "commit": "abc1234"}
REPO = Path(__file__).resolve().parents[2]


def _step(step_id: str, *, recorded: bool = True) -> Step:
    check = Check(step_id, f"{step_id} title", ("before line",), 5.0, (), lambda c, s, r: None)
    return Step(
        step_id, f"{step_id} title", 5.0, f"hands for {step_id}", check if recorded else None
    )


class Desk:
    """What surrounds the runner in a test: scripted answers and keys, fake launches and judge."""

    def __init__(self, clock: FakeClock, tmp_path: Path) -> None:
        self.clock = clock
        self.t0 = clock.now
        self.out = tmp_path / "sessions"
        self.ledger = tmp_path / "logs" / "acceptance.jsonl"
        self.answers: list[str] = []  # one per prompt; Enter once they run out
        self.keys: list[tuple[float, str]] = []  # (seconds after the start, key)
        self.runs: dict[str, list[Ran]] = {}  # scripted launches; default: a new session, code 0
        self.verdicts: dict[str, list[str]] = {}  # scripted judge outcomes; default: PASS
        self.prompts: list[str] = []
        self.said: list[str] = []
        self.launched: list[tuple[str, float]] = []  # (step id, seconds after the start)
        self.released: list[float] = []  # seconds after the start

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.answers.pop(0) if self.answers else ""

    def read_key(self) -> str | None:
        if self.keys and self.keys[0][0] <= self.clock.now - self.t0:
            return self.keys.pop(0)[1]
        return None

    def say(self, text: str = "", *, end: str = "\n") -> None:
        self.said.append(text)

    def launch(self, step: Step) -> Ran:
        self.launched.append((step.id, self.clock.now - self.t0))
        self.clock.advance(5.0)
        self.released.append(self.clock.now - self.t0)
        if self.runs.get(step.id):
            return self.runs[step.id].pop(0)
        return Ran(0, self.out / f"{step.id}-{len(self.launched)}" if step.check else None)

    def judge(self, check: Check, folder: Path) -> Verdict:
        scripted = self.verdicts.get(check.id)
        outcome = scripted.pop(0) if scripted else PASS
        mark = "ok" if outcome == PASS else "FAIL"
        lines = (f"[{mark}] judged {check.id}",)
        return Verdict(outcome, lines, {"m": 1.5}, folder, "3.1.19", "p1041", "MuseS-****")

    def sitting(self, steps: list[Step], **changes: Any) -> Sitting:
        setup: dict[str, Any] = {
            "run_id": RUN,
            "source": "athena",
            "versions": VERSIONS,
            "ledger": self.ledger,
            "launch": self.launch,
            "ask": self.ask,
            "read_key": self.read_key,
            "clock": self.clock,
            "sleep": self.clock.advance,
            "say": self.say,
            "judge": self.judge,
        }
        return Sitting(steps, **(setup | changes))

    def rows(self, kind: str = "attempt") -> list[dict[str, Any]]:
        return [r for r in read_rows(self.ledger) if r["kind"] == kind]

    def outcomes(self) -> list[tuple[str, str]]:
        return [(r["check"], r["outcome"]) for r in self.rows()]

    @property
    def text(self) -> str:
        return "\n".join(self.said)


@pytest.fixture
def desk(clock: FakeClock, tmp_path: Path) -> Desk:
    return Desk(clock, tmp_path)


# The plan ------------------------------------------------------------------------------------


def test_the_sitting_runs_hands_on_checks_first_and_hands_free_ones_last() -> None:
    ids = [s.id for s in plan([])]
    assert ids == ["P0", "H8", "H6", "H7", "H5", "F1", "H4", "H3", "H1/H2"]
    assert [s.id for s in plan([]) if s.check is None] == ["H3", "H1/H2"]


def test_no_h3_leaves_the_time_to_signal_step_out() -> None:
    assert "H3" not in [s.id for s in plan([], h3=False)]


def test_positional_checks_select_a_subset_in_the_sitting_order() -> None:
    assert [s.id for s in plan(["h4", "P0", "h1", "H2"])] == ["P0", "H4", "H1/H2"]


def test_an_unknown_check_is_refused_by_name() -> None:
    with pytest.raises(SittingError, match="H9"):
        plan(["P0", "H9"])


def test_a_plan_with_nothing_in_it_is_refused() -> None:
    with pytest.raises(SittingError, match="Nothing to run"):
        plan(["H3"], h3=False)


def test_h4_seconds_shortens_h4_and_nothing_else() -> None:
    short = {s.id: s for s in plan([], h4_seconds=30.0)}
    assert short["H4"].check is not None
    assert short["H4"].check.duration == 30.0
    assert short["H4"].seconds == 30.0
    assert short["H5"].check is CHECKS["H5"]


def test_every_check_runs_on_the_headband_whatever_the_platform() -> None:
    assert settled(plan([]), rehearse=False) == {}  # keys are read on Windows, macOS and Linux


def test_a_rehearsal_plays_the_keys_itself_and_skips_the_real_hardware_tests() -> None:
    rehearsed = settled(plan([]), rehearse=True)
    assert list(rehearsed) == ["H1/H2"]
    assert rehearsed["H1/H2"].outcome == SKIPPED


# The sitting ---------------------------------------------------------------------------------


def test_one_enter_starts_the_sitting_and_each_check_follows_its_countdown(desk: Desk) -> None:
    code = desk.sitting([_step("P0"), _step("H8"), _step("H3", recorded=False)]).run()

    assert code == 0
    assert len(desk.prompts) == 1
    assert [step_id for step_id, _ in desk.launched] == ["P0", "H8", "H3"]
    assert desk.outcomes() == [("P0", PASS), ("H8", PASS), ("H3", PASS)]
    for (_, started), released in zip(desk.launched[1:], desk.released, strict=False):
        assert started - released >= COOLDOWN_S - 1e-6  # the countdown is the Bluetooth cooldown
        assert started - released < COOLDOWN_S + 0.5


def test_the_desk_checklist_comes_before_the_one_enter(desk: Desk) -> None:
    said_at_the_prompt: list[str] = []

    def ask(prompt: str) -> str:
        said_at_the_prompt.append(desk.text)
        return ""

    desk.sitting([_step("P0"), _step("H8")], ask=ask).run()

    for needed in ("switched on", "Muse app", "dark cloth", "Do not click", "hands for P0"):
        assert needed in said_at_the_prompt[0]


def test_the_desk_checklist_on_screen_has_every_item_of_the_written_one(desk: Desk) -> None:
    desk.sitting([_step("P0")]).run()

    written = (REPO / "tests" / "hardware" / "README.md").read_text(encoding="utf-8")
    items = written.split("## On the desk before the start", 1)[1].split("##", 1)[0]
    assert items.count("\n- ") == 6
    on_screen = desk.text.split("On the desk before the start:", 1)[1].split("The plan", 1)[0]
    assert on_screen.count("\n  - ") == 6
    for needed in ("charged", "Muse app", "within 2 m", "dark cloth", "a lamp or a window",
                   "Do not click", "Nothing else is recording"):  # fmt: skip
        assert needed in on_screen
        assert needed in items


def test_the_checklist_says_how_to_get_out_of_a_text_selection(desk: Desk) -> None:
    desk.sitting([_step("P0")]).run()

    assert "If text gets highlighted, press Esc." in desk.text


def test_a_rehearsal_does_not_offer_keys_it_does_not_read(desk: Desk) -> None:
    desk.sitting([_step("P0"), _step("H8")], source="sim").run()

    assert "p pause" not in desk.text
    assert "Rehearsal: the keys are played for you. Close the window to stop." in desk.text


def test_a_run_started_right_after_another_waits_for_the_headband(desk: Desk) -> None:
    desk.sitting([_step("P0")], released=desk.clock.now - 3.0).run()

    assert desk.launched[0][1] == pytest.approx(COOLDOWN_S - 3.0, abs=0.3)
    assert "Next connect in" in desk.text


def test_a_run_started_long_after_the_last_one_does_not_wait(desk: Desk) -> None:
    desk.sitting([_step("P0")], released=desk.clock.now - 60.0).run()

    assert desk.launched[0][1] == 0.0
    assert "Next connect in" not in desk.text


def test_the_last_release_is_the_end_of_the_last_headband_run_in_the_log(tmp_path: Path) -> None:
    log = tmp_path / "connect.jsonl"
    assert last_release(log) is None

    def ran(at: str, source: str) -> ConnectRun:
        return ConnectRun(at, "record", source, None, "p1041", "signal", 4.0, 45.0)

    append_run(ran("2026-11-26T09:00:00", "athena"), log)
    append_run(ran("2026-11-26T10:00:00", "athena"), log)
    append_run(ran("2026-11-26T11:00:00", "sim"), log)  # the simulator holds no headband

    begun = datetime(2026, 11, 26, 10, 0, 0).timestamp()
    assert last_release(log) == begun + 45.0 + RELEASE_S


def test_the_intermission_shows_the_last_verdict_and_what_the_next_check_needs(desk: Desk) -> None:
    desk.sitting([_step("P0"), _step("H8")]).run()

    after_p0 = desk.text.split("P0: PASS", 1)[1]
    assert "Last: P0 PASS" in after_p0
    assert "hands for H8" in after_p0
    assert "p pause" in after_p0


def test_any_key_pauses_the_countdown_until_enter(desk: Desk) -> None:
    desk.keys = [(8.0, "x")]  # P0 records from 0 to 5 s, its countdown runs from 5 to 15 s

    code = desk.sitting([_step("P0"), _step("H8")]).run()

    assert code == 0
    assert len(desk.prompts) == 2
    assert "Paused" in desk.prompts[1]
    assert "before line" in desk.text  # a paused wearer gets the full explanation
    assert [step_id for step_id, _ in desk.launched] == ["P0", "H8"]


def test_s_in_the_countdown_skips_the_check(desk: Desk) -> None:
    desk.keys = [(8.0, "s")]

    code = desk.sitting([_step("P0"), _step("H8"), _step("H6")]).run()

    assert code == 1
    assert desk.outcomes() == [("P0", PASS), ("H8", SKIPPED), ("H6", PASS)]
    assert [step_id for step_id, _ in desk.launched] == ["P0", "H6"]


def test_q_ends_the_run_and_what_is_left_is_not_run(desk: Desk) -> None:
    desk.keys = [(8.0, "q")]

    code = desk.sitting([_step("P0"), _step("H8"), _step("H6")]).run()

    assert code == 1
    assert desk.outcomes() == [("P0", PASS), ("H8", NOT_RUN), ("H6", NOT_RUN)]
    assert [step_id for step_id, _ in desk.launched] == ["P0"]


def test_a_key_typed_during_a_recording_does_not_touch_the_next_countdown(desk: Desk) -> None:
    desk.keys = [(2.0, "q")]  # typed while P0 was recording: nothing was listening

    code = desk.sitting([_step("P0"), _step("H8")]).run()

    assert code == 0
    assert len(desk.prompts) == 1


def test_pause_asks_before_every_check_and_still_keeps_the_cooldown(desk: Desk) -> None:
    code = desk.sitting([_step("P0"), _step("H8")], pause=True).run()

    assert code == 0
    assert len(desk.prompts) == 2
    assert all("Enter = start" in p for p in desk.prompts)
    assert desk.launched[1][1] - desk.released[0] >= COOLDOWN_S - 1e-6


def test_a_fail_stops_and_waits_and_shows_how_to_judge_it_again(desk: Desk) -> None:
    desk.verdicts = {"P0": [FAIL]}

    code = desk.sitting([_step("P0"), _step("H8")]).run()

    assert code == 1
    assert "r = retry" in desk.prompts[1]
    session = desk.out / "P0-1"
    assert f"Saved session: {session}" in desk.text
    assert f'uv run python scripts/hw_acceptance.py --rejudge "{session}"' in desk.text
    assert desk.outcomes() == [("P0", FAIL), ("H8", PASS)]


def test_r_runs_the_check_again_after_the_cooldown_and_the_last_attempt_counts(desk: Desk) -> None:
    desk.verdicts = {"P0": [FAIL]}
    desk.answers = ["", "r"]

    code = desk.sitting([_step("P0")]).run()

    assert code == 0
    assert [(r["attempt"], r["outcome"]) for r in desk.rows()] == [(1, FAIL), (2, PASS)]
    assert desk.launched[1][1] - desk.released[0] >= COOLDOWN_S - 1e-6
    assert desk.rows("summary")[-1]["outcomes"] == {"P0": PASS}


def test_q_after_a_fail_ends_the_run(desk: Desk) -> None:
    desk.verdicts = {"P0": [FAIL]}
    desk.answers = ["", "q"]

    code = desk.sitting([_step("P0"), _step("H8")]).run()

    assert code == 1
    assert desk.outcomes() == [("P0", FAIL), ("H8", NOT_RUN)]


def test_a_failed_connect_is_tried_again_after_the_cooldown(desk: Desk) -> None:
    desk.runs = {"P0": [Ran(EXIT_CONNECT), Ran(EXIT_CONNECT)]}

    code = desk.sitting([_step("P0")]).run()

    assert code == 0
    assert [step_id for step_id, _ in desk.launched] == ["P0"] * 3
    for (_, started), released in zip(desk.launched[1:], desk.released, strict=False):
        assert started - released >= COOLDOWN_S - 1e-6
    assert desk.outcomes() == [("P0", PASS)]


def test_three_failed_connects_end_as_not_run_with_a_hint(desk: Desk) -> None:
    desk.runs = {"P0": [Ran(EXIT_CONNECT)] * 3}

    code = desk.sitting([_step("P0"), _step("H8")]).run()

    assert code == 1
    assert len([s for s, _ in desk.launched if s == "P0"]) == 3
    (row, _) = desk.rows()
    assert row["outcome"] == NOT_RUN
    assert "switched on" in row["lines"][0]
    assert "Muse" in row["lines"][0]
    assert "r = retry" in desk.prompts[1]  # it waits: the next check would not connect either


def test_a_recording_that_saved_nothing_fails_with_the_exit_code(desk: Desk) -> None:
    desk.runs = {"P0": [Ran(EXIT_WRITE)]}

    code = desk.sitting([_step("P0")]).run()

    assert code == 1
    (row,) = desk.rows()
    assert row["outcome"] == FAIL
    assert row["lines"] == [f"[FAIL] no session was saved (mufuse exited with code {EXIT_WRITE})"]
    assert row["session"] is None
    assert "--rejudge" not in desk.text  # nothing was saved to judge again


def test_an_unexpected_exit_code_is_kept_beside_the_verdict_on_what_was_saved(desk: Desk) -> None:
    desk.runs = {"P0": [Ran(EXIT_WRITE, desk.out / "partial")]}

    desk.sitting([_step("P0"), _step("H8")]).run()

    first, second = desk.rows()
    assert first["lines"] == ["[ok] judged P0", f"[note] mufuse exited with code {EXIT_WRITE}"]
    assert first["outcome"] == PASS  # the judges decide; the note is evidence
    assert second["lines"] == ["[ok] judged H8"]


def test_a_step_without_a_recording_is_judged_by_its_exit_code(desk: Desk) -> None:
    desk.runs = {"H3": [Ran(1, lines=("7/10 reached EEG",), measures={"h3.attempts": 10.0})]}

    code = desk.sitting([_step("H3", recorded=False)]).run()

    assert code == 1
    (row,) = desk.rows()
    assert row["outcome"] == FAIL
    assert row["lines"][0] == "7/10 reached EEG"
    assert "code 1" in row["lines"][-1]
    assert row["measures"] == {"h3.attempts": 10.0}


def test_exit_code_4_of_a_step_without_a_recording_is_not_a_connect_failure(desk: Desk) -> None:
    desk.runs = {"H1/H2": [Ran(4)]}  # pytest's own "usage error"

    desk.sitting([_step("H1/H2", recorded=False)]).run()

    assert len(desk.launched) == 1
    assert desk.outcomes() == [("H1/H2", FAIL)]


def test_a_check_settled_beforehand_gets_its_row_without_a_launch(desk: Desk) -> None:
    why = Verdict(NOT_RUN, ("no key reader here",))

    code = desk.sitting([_step("H6"), _step("H7")], settled={"H6": why}).run()

    assert code == 1
    assert [step_id for step_id, _ in desk.launched] == ["H7"]
    assert desk.outcomes() == [("H6", NOT_RUN), ("H7", PASS)]
    assert "no key reader here" in desk.text


# Evidence ------------------------------------------------------------------------------------


def test_each_attempt_is_a_row_a_later_reader_can_judge_from(desk: Desk) -> None:
    desk.sitting([_step("P0")]).run()

    (row,) = desk.rows()
    assert row["at"]
    del row["at"]
    assert row == {
        "run": RUN,
        "kind": "attempt",
        "check": "P0",
        "attempt": 1,
        "outcome": PASS,
        "lines": ["[ok] judged P0"],
        "measures": {"m": 1.5},
        "firmware": "3.1.19",
        "preset": "p1041",
        "device": "MuseS-****",  # the family only: not which headband
        "session": "P0-1",  # the folder's name: no user name or drive in the evidence
        "source": "athena",
        "mufuse": "0.1.0",
        "brainflow": "5.24.0",
        "commit": "abc1234",
    }


def test_the_verdict_is_saved_before_it_is_shown(desk: Desk) -> None:
    saved_when_shown: list[int] = []

    def say(text: str = "", *, end: str = "\n") -> None:
        if text.strip() == "P0: PASS":
            saved_when_shown.append(len(desk.rows()))

    desk.sitting([_step("P0")], say=say).run()

    assert saved_when_shown == [1]


def test_the_run_starts_and_ends_with_a_row_and_the_summary_lists_every_check(desk: Desk) -> None:
    desk.verdicts = {"H8": [FAIL]}
    desk.keys = [(25.0, "s")]

    code = desk.sitting([_step("P0"), _step("H8"), _step("H6")]).run()

    assert code == 1
    (start,) = desk.rows("run")
    assert start["checks"] == ["P0", "H8", "H6"]
    assert start["source"] == "athena"
    (summary,) = desk.rows("summary")
    assert summary["outcomes"] == {"P0": PASS, "H8": FAIL, "H6": SKIPPED}
    assert summary["passed"] is False
    shown = desk.text.split("Summary of run", 1)[1]
    for line in ("P0     PASS", "H8     FAIL", "H6     SKIPPED", "1 of 3 passed"):
        assert line in shown
    assert f"--resume {RUN}" in shown


def test_a_rehearsal_is_not_held_back_by_the_step_it_cannot_run(desk: Desk) -> None:
    known = {"H1/H2": Verdict(SKIPPED, ("the hardware tests need the real headband",))}
    steps = [_step("P0"), _step("H1/H2", recorded=False)]

    code = desk.sitting(steps, source="sim", settled=known).run()

    assert code == 0
    assert desk.rows("summary")[0]["passed"] is True
    shown = desk.text.split("Summary of run", 1)[1]
    assert "1 of 2 passed." in shown
    assert "H1/H2 does not count here: the hardware tests need the real headband." in shown


def test_a_rehearsal_still_fails_on_a_check_that_did_not_pass(desk: Desk) -> None:
    known = {"H1/H2": Verdict(SKIPPED, ("the hardware tests need the real headband",))}
    desk.verdicts = {"P0": [FAIL]}
    steps = [_step("P0"), _step("H1/H2", recorded=False)]

    assert desk.sitting(steps, source="sim", settled=known).run() == 1
    assert desk.rows("summary")[0]["passed"] is False


def test_a_rehearsal_says_that_it_is_not_hardware_evidence(desk: Desk) -> None:
    desk.sitting([_step("P0")], source="sim").run()

    assert desk.rows()[0]["source"] == "sim"
    assert "not hardware evidence" in desk.text


def test_only_a_folder_with_a_manifest_counts_as_the_new_session(tmp_path: Path) -> None:
    (tmp_path / "old").mkdir()
    (tmp_path / "old" / "manifest.json").write_text("{}")
    before = set(tmp_path.iterdir())
    assert new_session(tmp_path, before) is None

    (tmp_path / "zz-notes.txt").write_text("a stray file sorts last")
    (tmp_path / "zz-screenshots").mkdir()
    (tmp_path / "20261126T100000Z-ab12").mkdir()
    (tmp_path / "20261126T100000Z-ab12" / "manifest.json").write_text("{}")
    assert new_session(tmp_path, before) == tmp_path / "20261126T100000Z-ab12"


def _loaded(folder: Path) -> LoadedSession:
    device = {"firmware": "3.1.19", "preset": "p1041", "name": "MuseS-1A2B"}
    eeg = (np.zeros(1), np.zeros((1, 8)))  # one sample: an empty recording fails by itself
    return LoadedSession(folder, {"device": device}, {StreamKind.EEG: eeg}, [], [])


def test_a_judge_that_raises_becomes_a_fail_with_the_exception_text(tmp_path: Path) -> None:
    def broken(check: Check, session: LoadedSession, report: object) -> None:
        raise ZeroDivisionError("empty window")

    check = Check("H8", "title", (), 5.0, (), broken)

    verdict = judged(check, tmp_path, load=_loaded)

    assert verdict.outcome == FAIL
    assert verdict.lines == (
        "[FAIL] the session could not be judged: ZeroDivisionError: empty window",
    )
    assert verdict.session == tmp_path
    assert (verdict.firmware, verdict.preset, verdict.device) == ("3.1.19", "p1041", "MuseS-****")


def test_a_session_that_cannot_be_read_becomes_a_fail_too(tmp_path: Path) -> None:
    verdict = judged(CHECKS["P0"], tmp_path / "missing")

    assert verdict.outcome == FAIL
    assert "FileNotFoundError" in verdict.lines[0]


def test_a_judged_session_carries_its_lines_measures_and_firmware(tmp_path: Path) -> None:
    def judge(check: Check, session: LoadedSession, report: Any) -> None:
        report.check(True, "all good")
        report.measure("x", 2.0)

    verdict = judged(Check("P0", "title", (), 5.0, (), judge), tmp_path, load=_loaded)

    assert verdict == Verdict(
        PASS, ("[ok] all good",), {"x": 2.0}, tmp_path, "3.1.19", "p1041", "MuseS-****"
    )


def test_the_versions_name_the_operating_system_in_plain_words() -> None:
    made = versions(REPO)

    assert set(made) == {"mufuse", "brainflow", "commit", "os"}
    assert made["os"]
    assert all(part.replace(".", "").isalnum() for part in made["os"].split())


def test_a_torn_line_in_the_results_file_is_skipped(tmp_path: Path) -> None:
    ledger = tmp_path / "acceptance.jsonl"
    ledger.write_text('{"run": "a", "kind": "run"}\n{"run": "b", "ki\n[1]\n', encoding="utf-8")

    assert read_rows(ledger) == [{"run": "a", "kind": "run"}]
    assert read_rows(tmp_path / "none.jsonl") == []


# Resume --------------------------------------------------------------------------------------


# The report ----------------------------------------------------------------------------------


def _report(desk: Desk, run: str = RUN) -> Path:
    return desk.ledger.parent / "acceptance" / run / "report.md"


def test_the_run_ends_with_a_report_beside_the_results_file(desk: Desk) -> None:
    desk.verdicts = {"H8": [FAIL]}

    desk.sitting([_step("P0"), _step("H8")]).run()

    text = _report(desk).read_text(encoding="utf-8")
    assert text.startswith(f"# MuFuse hardware acceptance, run {RUN}")
    assert "1 of 2 requested checks passed" in text
    assert "MuseS-****, preset p1041, firmware 3.1.19" in text
    assert str(desk.out) not in text
    assert desk.out.parent.name not in text  # the folder pytest made for this test
    shown = desk.text.split("Summary of run", 1)[1]
    assert f"Report: {_report(desk)}" in shown
    assert "no paths, names, addresses or samples" in shown


def test_the_report_of_a_rehearsal_is_marked_and_names_its_short_h4(desk: Desk) -> None:
    desk.sitting(plan(["P0", "H4"], h4_seconds=30.0), source="sim").run()

    (start,) = desk.rows("run")
    assert start["h4_seconds"] == 30.0
    text = _report(desk).read_text(encoding="utf-8")
    assert "SIMULATOR REHEARSAL" in text
    assert "--rehearse --h4-seconds 30 P0 H4" in text


def test_a_sitting_with_the_full_h4_does_not_note_a_length(desk: Desk) -> None:
    desk.sitting(plan(["H4"])).run()

    assert "h4_seconds" not in desk.rows("run")[0]


def test_the_report_lists_the_checks_in_the_sitting_order() -> None:
    assert tuple(s.id for s in STEPS) == ORDER


def test_every_reason_the_runner_gives_is_one_the_report_prints(desk: Desk) -> None:
    desk.runs = {"P0": [Ran(EXIT_CONNECT)] * 3}
    desk.answers = ["", "", "s", "q"]  # start, continue after P0, skip H8, quit at H6
    steps = [_step(c) for c in ("P0", "H8", "H6", "H7")]
    desk.sitting(steps, pause=True).run()
    known = settled(plan([]), rehearse=True)

    given = [r["lines"][0] for r in desk.rows()] + [v.lines[0] for v in known.values()]

    assert [r["outcome"] for r in desk.rows()] == [NOT_RUN, SKIPPED, NOT_RUN, NOT_RUN]
    assert len(set(given)) == 4
    assert ENDED in given
    assert set(given) <= set(REASONS)


def test_a_run_id_that_is_not_a_plain_name_gets_no_report(desk: Desk) -> None:
    desk.sitting([_step("P0")]).run()

    assert write_report(desk.ledger, "../elsewhere", desk.say) is None
    assert write_report(desk.ledger, "a/b", desk.say) is None
    assert [p.name for p in (desk.ledger.parent / "acceptance").iterdir()] == [RUN]
    assert sorted(p.name for p in desk.ledger.parent.iterdir()) == [
        "acceptance",
        "acceptance.jsonl",
    ]


def test_a_report_that_cannot_be_written_is_said_and_does_not_change_the_result(
    desk: Desk, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(rows: object, run: str) -> str:
        raise ValueError("no table")

    monkeypatch.setattr("mufuse.sitting.render", broken)

    code = desk.sitting([_step("P0")]).run()

    assert code == 0
    assert not _report(desk).exists()
    assert "The report could not be written: ValueError: no table" in desk.text


def test_judging_again_writes_the_report_again(desk: Desk) -> None:
    folder = _saved(desk.out, "H8-1", f"H8 acceptance {RUN}")
    desk.verdicts = {"H8": [FAIL]}
    desk.runs = {"H8": [Ran(0, folder)]}
    desk.sitting([_step("H8")]).run()
    assert "| FAIL | 1 |" in _report(desk).read_text(encoding="utf-8")
    desk.said.clear()

    rejudge(
        [RUN, str(folder)],
        out=desk.out,
        ledger=desk.ledger,
        versions=VERSIONS,
        say=desk.say,
        clock=desk.clock,
        judge=desk.judge,
    )

    text = _report(desk).read_text(encoding="utf-8")
    assert "| PASS (judged again; FAIL when recorded) | 1 |" in text
    assert desk.text.count("Report: ") == 1  # once per run, however many of its sessions


def _earlier_runs(desk: Desk) -> None:
    """An athena run with a pass, a fail and a skip, then a later rehearsal."""
    desk.verdicts = {"H8": [FAIL]}
    desk.answers = ["", "", "", "s"]  # start P0, start H8, continue after its FAIL, skip H6
    desk.sitting([_step("P0"), _step("H8"), _step("H6")], pause=True, run_id="A").run()
    desk.sitting([_step("P0")], run_id="B", source="sim").run()


def test_resume_takes_the_latest_athena_run_and_only_what_has_not_passed(desk: Desk) -> None:
    _earlier_runs(desk)

    history = to_resume(read_rows(desk.ledger), None, "athena")

    assert history[0]["run"] == "A"
    assert standing(history, "athena") == {"P0": PASS, "H8": FAIL, "H6": SKIPPED}

    desk.launched.clear()
    code = desk.sitting([_step("H8"), _step("H6")], run_id="A", history=history).run()

    assert code == 0
    assert [step_id for step_id, _ in desk.launched] == ["H8", "H6"]
    assert [(r["check"], r["attempt"]) for r in desk.rows() if r["run"] == "A"][-2:] == [
        ("H8", 2),
        ("H6", 2),
    ]
    assert len([r for r in desk.rows("run") if r["run"] == "A"]) == 1
    last = [r for r in desk.rows("summary") if r["run"] == "A"][-1]
    assert last["outcomes"] == {"P0": PASS, "H8": PASS, "H6": PASS}
    assert last["passed"] is True


def test_resume_refuses_to_mix_the_simulator_with_the_headband(desk: Desk) -> None:
    _earlier_runs(desk)
    rows = read_rows(desk.ledger)

    with pytest.raises(SittingError, match="sim"):
        to_resume(rows, "B", "athena")
    with pytest.raises(SittingError, match="athena"):
        to_resume(rows, "A", "sim")
    assert to_resume(rows, "B", "sim")[0]["run"] == "B"


def test_resume_says_so_when_there_is_no_such_run(desk: Desk) -> None:
    with pytest.raises(SittingError, match="no athena run"):
        to_resume([], None, "athena")
    _earlier_runs(desk)
    with pytest.raises(SittingError, match="Run C"):
        to_resume(read_rows(desk.ledger), "C", "athena")


def test_a_sim_row_never_counts_as_hardware_evidence() -> None:
    rows: list[dict[str, Any]] = [
        {"run": "A", "kind": "run", "checks": ["H8"], "source": "athena"},
        {"run": "A", "kind": "attempt", "check": "H8", "outcome": FAIL, "source": "athena"},
        {"run": "A", "kind": "rejudge", "check": "H8", "outcome": PASS, "source": "sim"},
    ]

    assert standing(rows, "athena") == {"H8": FAIL}


def test_a_check_with_no_row_at_all_still_shows_in_a_resumed_summary(desk: Desk) -> None:
    rows: list[dict[str, Any]] = [  # the window was closed during P0
        {"run": "A", "kind": "run", "checks": ["P0", "H8"], "source": "athena"},
    ]

    code = desk.sitting([_step("P0")], run_id="A", history=rows).run()

    assert code == 1
    assert desk.rows("summary")[-1]["outcomes"] == {"P0": PASS, "H8": NOT_RUN}


# Re-judge ------------------------------------------------------------------------------------


def _saved(out: Path, name: str, notes: str, driver: str = "brainflow-5.24.0") -> Path:
    folder = out / name
    folder.mkdir(parents=True)
    manifest = {"notes": notes, "device": {"driver": driver, "firmware": "3.1.19"}}
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return folder


def test_rejudge_appends_a_marked_row_and_overwrites_nothing(desk: Desk) -> None:
    folder = _saved(desk.out, "H8-1", f"H8 acceptance {RUN}")
    desk.verdicts = {"H8": [FAIL]}
    desk.runs = {"H8": [Ran(0, folder)]}
    desk.sitting([_step("H8")]).run()
    earlier = desk.ledger.read_text(encoding="utf-8")

    code = rejudge(
        [str(folder)],
        out=desk.out,
        ledger=desk.ledger,
        versions=VERSIONS | {"commit": "def5678"},
        say=desk.say,
        clock=desk.clock,
        judge=desk.judge,
    )

    assert code == 0
    assert desk.ledger.read_text(encoding="utf-8").startswith(earlier)
    (row,) = desk.rows("rejudge")
    assert (row["run"], row["check"], row["attempt"]) == (RUN, "H8", 1)
    assert (row["outcome"], row["session"], row["source"]) == (PASS, "H8-1", "athena")
    assert row["commit"] == "def5678"
    assert "H8: PASS" in desk.text
    assert standing(read_rows(desk.ledger), "athena") == {"H8": PASS}  # the last row counts


def test_rejudge_of_a_run_takes_the_last_session_of_each_check(desk: Desk) -> None:
    first = _saved(desk.out, "H8-1", f"H8 acceptance {RUN}")
    second = _saved(desk.out, "H8-2", f"H8 acceptance {RUN}")
    p0 = _saved(desk.out, "P0-3", f"P0 acceptance {RUN}")
    desk.verdicts = {"H8": [FAIL, FAIL, FAIL]}
    desk.runs = {"H8": [Ran(0, first), Ran(0, second)], "P0": [Ran(0, p0)]}
    desk.answers = ["", "r"]
    desk.sitting([_step("H8"), _step("P0")]).run()

    code = rejudge(
        [RUN], out=desk.out, ledger=desk.ledger, versions=VERSIONS, say=desk.say, judge=desk.judge
    )

    assert code == 1
    assert [
        (r["check"], r["session"], r["attempt"], r["outcome"]) for r in desk.rows("rejudge")
    ] == [
        ("H8", "H8-2", 2, FAIL),
        ("P0", "P0-3", 1, PASS),
    ]


def test_rejudge_reports_what_is_not_an_acceptance_session(desk: Desk) -> None:
    plain = _saved(desk.out, "plain", "an evening recording")
    (desk.out / "empty").mkdir()

    code = rejudge(
        [str(plain), "empty", "20990101-000000"],
        out=desk.out,
        ledger=desk.ledger,
        versions=VERSIONS,
        say=desk.say,
        judge=desk.judge,
    )

    assert code == 1
    assert read_rows(desk.ledger) == []
    assert desk.text.count("not an acceptance session") == 2
    assert "20990101-000000" in desk.text


def test_rejudge_says_where_it_looked_when_the_sessions_of_a_run_are_elsewhere(desk: Desk) -> None:
    folder = _saved(desk.out, "H8-1", f"H8 acceptance {RUN}")
    desk.runs = {"H8": [Ran(0, folder)]}
    desk.sitting([_step("H8")]).run()
    elsewhere = desk.out.parent / "elsewhere"

    code = rejudge(
        [RUN], out=elsewhere, ledger=desk.ledger, versions=VERSIONS, say=desk.say, judge=desk.judge
    )

    assert code == 1
    assert desk.rows("rejudge") == []
    assert f"no session folder H8-1 under {elsewhere}" in desk.text
    assert "--out" in desk.text
    assert "not an acceptance session" not in desk.text


def test_a_rehearsal_session_is_only_rejudged_into_the_results_file_of_its_run(desk: Desk) -> None:
    _saved(desk.out, "sim-h8", "H8 acceptance R1", driver="simulated")

    code = rejudge(
        ["sim-h8"], out=desk.out, ledger=desk.ledger, versions=VERSIONS, say=desk.say,
        judge=desk.judge,
    )  # fmt: skip

    assert code == 1
    assert read_rows(desk.ledger) == []  # nothing of a rehearsal lands in another log folder
    assert "MUFUSE_LOG_DIR" in desk.text
    assert not (desk.ledger.parent / "acceptance").exists()


def test_a_rejudged_rehearsal_takes_the_length_of_its_h4_from_the_run(desk: Desk) -> None:
    desk.sitting(plan(["H4"], h4_seconds=30.0), source="sim", run_id="R1").run()
    _saved(desk.out, "sim-h4", "H4 acceptance R1", driver="simulated")
    durations: list[float] = []

    def judge(check: Check, folder: Path) -> Verdict:
        durations.append(check.duration)
        return Verdict(PASS, (), {}, folder, None)

    rejudge(
        ["sim-h4"], out=desk.out, ledger=desk.ledger, versions=VERSIONS, say=desk.say, judge=judge
    )

    assert durations == [30.0]


def test_a_simulated_session_is_rejudged_as_sim_and_only_it_may_have_a_short_h4(desk: Desk) -> None:
    desk.sitting([_step("H4")], source="sim", run_id="R1").run()
    _saved(desk.out, "sim-h4", "H4 acceptance R1", driver="simulated")
    _saved(desk.out, "real-h4", "H4 acceptance R2")
    durations: list[float] = []

    def judge(check: Check, folder: Path) -> Verdict:
        durations.append(check.duration)
        return Verdict(PASS, (), {}, folder, None)

    rejudge(
        ["sim-h4", "real-h4"],
        out=desk.out,
        ledger=desk.ledger,
        versions=VERSIONS,
        say=desk.say,
        judge=judge,
        h4_seconds=30.0,
    )

    assert durations == [30.0, 600.0]
    assert [(r["run"], r["source"], r["attempt"]) for r in desk.rows("rejudge")] == [
        ("R1", "sim", None),
        ("R2", "athena", None),
    ]


# The launcher --------------------------------------------------------------------------------


class Spawned:
    """A fake child process: remembers how it was started and leaves a session behind."""

    def __init__(self, out: Path | None = None, code: int = 0) -> None:
        self.out = out
        self.code = code
        self.cmd: list[str] = []
        self.env: dict[str, str] = {}
        self.cwd: Path | None = None
        self.guide: dict[str, Any] = {}

    def __call__(self, cmd: list[str], env: dict[str, str], cwd: Path | None) -> int:
        self.cmd, self.env, self.cwd = cmd, env, cwd
        if "MUFUSE_GUIDE" in env:
            self.guide = json.loads(Path(env["MUFUSE_GUIDE"]).read_text(encoding="utf-8"))
        if self.out is not None:
            (self.out / "zz-stray.txt").write_text("not a session")
            (self.out / "20261126T100000Z-ab12").mkdir()
            (self.out / "20261126T100000Z-ab12" / "manifest.json").write_text("{}")
        return self.code


def _launcher(tmp_path: Path, spawn: Spawned, **changes: Any) -> Launcher:
    setup: dict[str, Any] = {
        "exe": "mufuse",
        "repo": tmp_path / "repo",
        "out": tmp_path / "sessions",
        "run": RUN,
        "source": "athena",
        "device": None,
        "env": {"PYTHONUTF8": "1"},
        "connect_log": tmp_path / "logs" / "connect.jsonl",
        "spawn": spawn,
    }
    return Launcher(**(setup | changes))


def test_a_check_is_one_guided_recording_tagged_with_the_check_and_the_run(tmp_path: Path) -> None:
    out = tmp_path / "sessions"
    spawn = Spawned(out)
    (h6,) = plan(["H6"])

    ran = _launcher(tmp_path, spawn, device="MuseS-1A2B")(h6)

    assert spawn.cmd == [
        "mufuse", "record", "--source", "athena", "--duration", "40.0",
        "--notes", f"H6 acceptance {RUN}", "--out", str(out), "--device", "MuseS-1A2B",
    ]  # fmt: skip
    assert spawn.env["MUFUSE_RUN_LABEL"] == f"H6 {RUN}"
    assert spawn.env["PYTHONUTF8"] == "1"
    assert "MUFUSE_SIM_WEARER" not in spawn.env
    assert spawn.guide["duration"] == 40.0
    assert ran == Ran(0, out / "20261126T100000Z-ab12")


def test_a_rehearsal_gives_each_recording_its_simulated_wearer(tmp_path: Path) -> None:
    spawn = Spawned(code=EXIT_CONNECT)
    (h5,) = plan(["H5"])

    ran = _launcher(tmp_path, spawn, source="sim")(h5)

    assert spawn.cmd[2:4] == ["--source", "sim"]
    assert spawn.env["MUFUSE_SIM_WEARER"] == "H5"
    assert ran == Ran(EXIT_CONNECT, None)


def test_h3_reuses_the_time_to_signal_script_and_keeps_what_it_measured(tmp_path: Path) -> None:
    log = tmp_path / "logs" / "connect.jsonl"

    def attempt(seconds: float | None, label: str) -> ConnectRun:
        outcome = "signal" if seconds is not None else "connect_error"
        return ConnectRun("2026-11-26T10:00:00", "stream", "sim", None, "p1041", outcome, seconds,
                          3.0, label=label)  # fmt: skip

    append_run(attempt(2.0, "P0 earlier"), log)

    class H3(Spawned):
        def __call__(self, cmd: list[str], env: dict[str, str], cwd: Path | None) -> int:
            append_run(attempt(4.25, "H3 x 1/3"), log)
            append_run(attempt(None, "H3 x 2/3"), log)
            append_run(attempt(16.0, "H3 x 3/3"), log)
            return super().__call__(cmd, env, cwd)

    spawn = H3(code=1)
    (h3,) = plan(["H3"])

    ran = _launcher(tmp_path, spawn, source="sim", device="MuseS-1A2B")(h3)

    script = tmp_path / "repo" / "scripts" / "h3_time_to_signal.py"
    assert spawn.cmd == [sys.executable, str(script), "--source", "sim", "--device", "MuseS-1A2B"]
    assert ran.code == 1
    assert ran.session is None
    assert ran.lines == (
        "1/3: EEG after 4.2 s",
        "2/3: connect_error",
        "3/3: EEG after 16.0 s",
        "1 of 3 attempts reached EEG within 15 s",
    )
    assert ran.measures == {"h3.attempts": 3.0, "h3.within_15_s": 1.0, "h3.slowest_s": 16.0}


def test_h1_and_h2_are_the_hardware_tests_run_from_the_repository(tmp_path: Path) -> None:
    spawn = Spawned()
    steps = plan(["H1/H2"])

    ran = _launcher(tmp_path, spawn)(steps[0])

    assert spawn.cmd == [sys.executable, "-m", "pytest", "-m", "hardware", "-s"]
    assert spawn.cwd == tmp_path / "repo"
    assert ran == Ran(0)


def test_a_child_process_hands_back_its_exit_code() -> None:
    assert _spawn([sys.executable, "-c", "import sys; sys.exit(3)"], dict(os.environ), None) == 3


# Prompts and the command line ----------------------------------------------------------------


class _Stdin:
    def __init__(self, tty: bool) -> None:
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def test_ctrl_c_at_a_prompt_asks_again_on_a_terminal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    typed: list[Any] = [EOFError(), KeyboardInterrupt(), " R \n"]

    def fake_input(prompt: str) -> str:
        answer = typed.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr("sys.stdin", _Stdin(tty=True))

    assert _ask("r = retry: ") == "r"
    assert capsys.readouterr().out.count("Ctrl+C does nothing here") == 2


def test_a_closed_input_quits_instead_of_asking_forever(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_input(prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr("sys.stdin", _Stdin(tty=False))

    assert _ask("Enter = start: ") == "q"


def test_the_command_refuses_an_unknown_check(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["H9"], repo=REPO) == 2
    assert "H9" in capsys.readouterr().out


def test_a_short_h4_is_only_for_a_rehearsal(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--h4-seconds", "30", "H4"], repo=REPO) == 2
    assert "rehearsal" in capsys.readouterr().out


def test_the_command_says_so_when_mufuse_is_not_on_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python"))  # and none beside this

    assert main(["--rehearse", "P0"], repo=REPO) == 2
    assert "uv run python scripts/hw_acceptance.py" in capsys.readouterr().out


def test_mufuse_beside_the_interpreter_is_used_when_it_is_not_on_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: FakeClock
) -> None:
    beside = tmp_path / "venv" / ("mufuse.exe" if sys.platform == "win32" else "mufuse")
    beside.parent.mkdir()
    beside.write_text("")
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr(sys, "executable", str(beside.with_name("python")))
    spawn = Spawned()

    main(
        ["--rehearse", "P0", "--out", str(tmp_path / "out")],
        repo=REPO,
        spawn=spawn,
        clock=clock,
        sleep=clock.advance,
    )

    assert spawn.cmd[0] == str(beside)


def test_resume_takes_its_checks_from_the_run_not_from_the_command_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["H5", "--resume"], repo=REPO) == 2
    assert "--resume" in capsys.readouterr().out


def test_the_command_refuses_to_resume_when_there_is_nothing_to_resume(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--resume"], repo=REPO) == 2
    assert "no athena run" in capsys.readouterr().out


def test_a_rehearsal_given_no_folders_keeps_to_a_scratch_folder_of_its_own(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clock: FakeClock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("MUFUSE_LOG_DIR")
    monkeypatch.setenv("MUFUSE_SIM_WEARER", "H8:idle")  # left over in the shell
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    spawn = Spawned()

    code = main(["--rehearse", "P0"], repo=REPO, spawn=spawn, clock=clock, sleep=clock.advance)

    assert code == 1  # the fake child saved nothing
    (scratch,) = tmp_path.glob("mufuse-rehearsal-*")
    options = dict(zip(spawn.cmd[2::2], spawn.cmd[3::2], strict=True))
    assert Path(options["--out"]) == scratch / "sessions"
    assert Path(spawn.env["MUFUSE_LOG_DIR"]) == scratch / "logs"
    assert spawn.env["MUFUSE_SIM_WEARER"] == "P0"
    assert [r["kind"] for r in read_rows(scratch / "logs" / "acceptance.jsonl")] == [
        "run",
        "attempt",
        "summary",
    ]
    shown = capsys.readouterr().out
    assert "no session was saved" in shown
    # ... and says what a later --resume or --rejudge of it needs
    assert f"MUFUSE_LOG_DIR to {scratch / 'logs'}" in shown
    assert f"--out {scratch / 'sessions'}" in shown


def test_a_rehearsal_is_only_resumed_where_it_ran(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))

    assert main(["--rehearse", "--resume"], repo=REPO) == 2  # --out is missing

    shown = capsys.readouterr().out
    assert "MUFUSE_LOG_DIR" in shown
    assert "--out" in shown
    assert list(tmp_path.glob("mufuse-rehearsal-*")) == []  # no new, empty scratch folder


def test_a_resumed_rehearsal_keeps_the_length_of_its_h4(tmp_path: Path, clock: FakeClock) -> None:
    out = ["--out", str(tmp_path / "out")]
    spawn = Spawned()
    main(
        ["--rehearse", "--h4-seconds", "30", "H4", *out],
        repo=REPO,
        spawn=spawn,
        clock=clock,
        sleep=clock.advance,
    )
    spawn.cmd = []

    main(["--rehearse", "--resume", *out], repo=REPO, spawn=spawn, clock=clock, sleep=clock.advance)

    options = dict(zip(spawn.cmd[2::2], spawn.cmd[3::2], strict=True))
    assert options["--duration"] == "30.0"


def test_a_new_headband_run_reads_when_the_headband_was_last_let_go(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clock: FakeClock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    begun = datetime.fromtimestamp(clock.now - 20.0).isoformat(timespec="seconds")
    append_run(ConnectRun(begun, "record", "athena", None, "p1041", "signal", 4.0, 15.0))
    monkeypatch.setattr("builtins.input", lambda prompt: "")  # Enter at every prompt
    spawn = Spawned()

    main(["P0", "--out", str(tmp_path / "out")], repo=REPO, spawn=spawn, clock=clock,
         sleep=clock.advance)  # fmt: skip

    assert spawn.cmd[1] == "record"
    assert "Next connect in 13 s" in capsys.readouterr().out  # 8 s release + 10 s, 5 s ago


class _Console:
    """Stands in for kernel32 on a Windows console whose input mode is `mode`."""

    def __init__(self, mode: int | None) -> None:
        self.mode = mode
        self.set: list[int] = []

    def GetStdHandle(self, which: int) -> int:  # noqa: N802
        return 7

    def GetConsoleMode(self, handle: int, ref: Any) -> int:  # noqa: N802
        if self.mode is None:
            return 0  # not a console
        ref._obj.value = self.mode
        return 1

    def SetConsoleMode(self, handle: int, mode: int) -> int:  # noqa: N802
        self.set.append(mode)
        return 1


def test_a_click_cannot_start_a_text_selection_during_the_run() -> None:
    console = _Console(0x01F7)  # quick edit on, as a Windows console starts

    restore = _selection_off(console)

    assert console.set == [0x01B7]  # quick edit off, extended flags kept on
    restore()
    assert console.set == [0x01B7, 0x01F7]


def test_where_there_is_no_console_nothing_is_changed() -> None:
    console = _Console(None)

    _selection_off(console)()

    assert console.set == []
