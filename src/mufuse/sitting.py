"""One sitting for every hardware acceptance check of feature 001.

    uv run python scripts/hw_acceptance.py                 # the whole sitting
    uv run python scripts/hw_acceptance.py H5 F1           # just these
    uv run python scripts/hw_acceptance.py --resume        # what the last run did not pass
    uv run python scripts/hw_acceptance.py --rejudge RUN   # judge saved sessions again
    uv run python scripts/hw_acceptance.py --rehearse      # all of it on the simulator

The checks that need hands come first (P0, H8, H6, H7, H5, F1), the hands-free ones last (H4,
H3, H1/H2). After one Enter each check starts by itself after a 10 s countdown, which is also
the pause the headband needs between a release and the next connect. A FAIL always stops and
waits. Every attempt is one row in `acceptance.jsonl` beside the connection log, written before
its verdict is shown, and every recording stays on disk so it can be judged again later
without the headband. The run ends with a report of its numbers, `acceptance/<run>/report.md`
beside that file, that holds nothing personal and can be pasted into the pull request.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any, Protocol

from mufuse.acceptance import CHECKS, Check
from mufuse.acceptance_report import COMMAND, mask_device, render
from mufuse.cli import EXIT_CONNECT, use_utf8_output
from mufuse.recording.reader import LoadedSession, load_session
from mufuse.runlog import log_path, read_runs, summarize

PASS, FAIL, SKIPPED, NOT_RUN = "PASS", "FAIL", "SKIPPED", "NOT RUN"
COOLDOWN_S = 10.0  # from a release of the headband to the next connect; also the intermission
RELEASE_S = 8.0  # about how long the headband takes to let go once a run is in the log
CONNECT_TRIES = 3
H3_WITHIN_S = 15.0  # SC-001, as in scripts/h3_time_to_signal.py, whose exit code is the verdict
ENDED = "the run was ended before this check"

Row = dict[str, Any]  # one line of acceptance.jsonl


class SittingError(Exception):
    """The sitting cannot start as asked; the message is for the person at the keyboard."""


class Say(Protocol):
    def __call__(self, text: str = "", *, end: str = "\n") -> None: ...


@dataclass(frozen=True)
class Step:
    id: str
    title: str
    seconds: float  # about how long it takes once it has started
    needs: str  # one line for the intermission: what it needs and where the hands go
    check: Check | None = None  # None: its own command is the judge (H3, H1/H2)


@dataclass(frozen=True)
class Ran:
    """What a launched step left behind."""

    code: int
    session: Path | None = None
    lines: tuple[str, ...] = ()
    measures: dict[str, float] = field(default_factory=dict[str, float])


@dataclass(frozen=True)
class Verdict:
    outcome: str  # PASS, FAIL, SKIPPED or NOT RUN
    lines: tuple[str, ...] = ()
    measures: dict[str, float] = field(default_factory=dict[str, float])
    session: Path | None = None
    firmware: str | None = None
    preset: str | None = None
    device: str | None = None  # masked: the family of the headband, not which one


# The plan ------------------------------------------------------------------------------------

_NEEDS = {
    "P0": "Headband on the head. Both hands adjust the fit for 15 s, then rest.",
    "H8": "Headband on. One hand near the LEFT ear sensor: it is lifted off the skin, then let "
    "back.",
    "H6": "Headband on. One finger over SPACE. This window stays focused.",
    "H7": "Headband on. Fingers over Ctrl and C: one tap when told. No click in the window.",
    "H5": "Headband on. One finger on the headband's power button: off, about 10 s, on.",
    "F1": "Dark cloth within reach. The headband comes off here and faces a lamp or a window.",
    "H4": "Hands free from here. Headband switched on, worn or on the desk within 2 m. Nothing "
    "to press.",
}
# In running order: CHECKS is hands-on first with H4 last, then the two steps that only connect.
STEPS: tuple[Step, ...] = (
    *(Step(c.id, c.title, c.duration, _NEEDS[c.id], c) for c in CHECKS.values()),
    Step(
        "H3",
        "Time to first signal, 10 connects in a row (SC-001)",
        300.0,
        "Hands free. Headband switched on within 2 m. It connects ten times by itself.",
    ),
    Step(
        "H1/H2",
        "Discovery and 30 s of every stream",
        60.0,
        "Hands free. Headband switched on within 2 m. The hardware tests run by themselves.",
    ),
)
_ALIASES = {"H1": "H1/H2", "H2": "H1/H2", "H1H2": "H1/H2"}


def plan(
    selected: Sequence[str], *, h3: bool = True, h4_seconds: float | None = None
) -> list[Step]:
    """The steps of a sitting, in the sitting order whatever order they were named in."""
    wanted = [_ALIASES.get(s.upper(), s.upper()) for s in selected]
    known = [s.id for s in STEPS]
    unknown = [w for w in wanted if w not in known]
    if unknown:
        raise SittingError(
            f"Unknown check(s): {', '.join(unknown)}. Choose from {', '.join(known)}."
        )
    steps = [s for s in STEPS if (not wanted or s.id in wanted) and (h3 or s.id != "H3")]
    if not steps:
        raise SittingError("Nothing to run.")
    if h4_seconds is not None:
        short = replace(CHECKS["H4"], duration=h4_seconds)
        steps = [replace(s, seconds=h4_seconds, check=short) if s.id == "H4" else s for s in steps]
    return steps


def settled(
    steps: Sequence[Step], *, rehearse: bool, platform: str = sys.platform
) -> dict[str, Verdict]:
    """The steps whose outcome is known before the sitting starts, with the reason."""
    known: dict[str, Verdict] = {}
    for step in steps:
        if step.id == "H6" and not rehearse and platform != "win32":
            why = "SPACE presses are only read on Windows; H6 needs a Windows terminal"
            known[step.id] = Verdict(NOT_RUN, (why,))
        if step.id == "H1/H2" and rehearse:
            known[step.id] = Verdict(SKIPPED, ("the hardware tests need the real headband",))
    return known


# Evidence ------------------------------------------------------------------------------------


def new_session(out: Path, before: set[Path]) -> Path | None:
    """The session folder a recording added to `out`. Only a folder with a manifest counts:
    anything else that appeared there meanwhile is not a session."""
    new = sorted(p for p in set(out.iterdir()) - before if (p / "manifest.json").is_file())
    return new[-1] if new else None


def judged(
    check: Check, folder: Path, load: Callable[[Path], LoadedSession] = load_session
) -> Verdict:
    """The verdict on a saved session. A reader or judge that raises is a FAIL with the
    exception text, never the end of the sitting: the session stays on disk to judge again."""
    worn: tuple[str | None, str | None, str | None] = (None, None, None)
    try:
        session = load(folder)
        device: dict[str, Any] = session.manifest.get("device") or {}
        worn = (device.get("firmware"), device.get("preset"), mask_device(device.get("name")))
        result = check.evaluate(session)
    except Exception as exc:
        line = f"[FAIL] the session could not be judged: {type(exc).__name__}: {exc}"
        return Verdict(FAIL, (line,), {}, folder, *worn)
    return Verdict(PASS if result.passed else FAIL, result.lines, result.measures, folder, *worn)


def read_rows(path: Path) -> list[Row]:
    if not path.exists():
        return []
    rows: list[Row] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue  # a line torn by a crash mid-write
        if isinstance(row, dict):
            rows.append(row)  # pyright: ignore[reportUnknownArgumentType]
    return rows


def _append(path: Path, row: Row) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def _attempt_row(
    kind: str,
    run: str,
    at: float,
    check_id: str,
    attempt: int | None,
    verdict: Verdict,
    source: str,
    versions: Mapping[str, str | None],
) -> Row:
    return {
        "run": run,
        "at": _iso(at),
        "kind": kind,
        "check": check_id,
        "attempt": attempt,
        "outcome": verdict.outcome,
        "lines": list(verdict.lines),
        "measures": verdict.measures,
        "firmware": verdict.firmware,
        "preset": verdict.preset,
        "device": verdict.device,
        "session": verdict.session.name if verdict.session else None,  # never a personal path
        "source": source,
        **versions,
    }


def versions(repo: Path) -> dict[str, str | None]:
    """What produced a verdict: the two packages, the commit the judges were at and the
    operating system."""
    cmd = ["git", "-C", str(repo), "describe", "--always", "--dirty", "--exclude", "*"]
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
        commit = done.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        commit = None
    return {
        "mufuse": version("mufuse"),
        "brainflow": version("brainflow"),
        "commit": commit,
        "os": f"{platform.system()} {platform.release()}",
    }


_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")  # it names a folder


def write_report(ledger: Path, run: str, say: Say) -> Path | None:
    """Write the report of `run` to `acceptance/<run>/report.md` beside the results file and
    say where it is. A report that cannot be made is said, never raised: the verdicts are
    already saved and the run's result does not depend on it."""
    if not _RUN_ID.fullmatch(run):
        return None
    path = ledger.parent / "acceptance" / run / "report.md"
    try:
        text = render(read_rows(ledger), run)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    except Exception as exc:
        say(f"The report could not be written: {type(exc).__name__}: {exc}")
        return None
    say(f"Report: {path}")
    say("  It holds no paths, names, addresses or samples: it can go into the pull request.")
    return path


def last_release(connect_log: Path) -> float | None:
    """When the headband was last let go, going by the connection log: the end of its last
    run there plus the release that follows it. None when the log has no headband run."""
    runs = [r for r in read_runs(connect_log) if r.source == "athena"]
    if not runs:
        return None
    return datetime.fromisoformat(runs[-1].at).timestamp() + runs[-1].elapsed_s + RELEASE_S


def standing(rows: Sequence[Row], source: str) -> dict[str, str]:
    """Where each check stands: its last attempt or re-judgement counts. Rows of another
    source are left out, so a simulated row never stands in for the headband."""
    return {
        r["check"]: r["outcome"]
        for r in rows
        if r.get("kind") in ("attempt", "rejudge") and r.get("source") == source
    }


def to_resume(rows: Sequence[Row], run: str | None, source: str) -> list[Row]:
    """The rows of the run to resume, its start row first: `run`, or the latest `source` run."""
    starts = [r for r in rows if r.get("kind") == "run"]
    if run is None:
        start = next((r for r in reversed(starts) if r.get("source") == source), None)
        if start is None:
            raise SittingError(f"There is no {source} run to resume.")
    else:
        start = next((r for r in starts if r.get("run") == run), None)
        if start is None:
            raise SittingError(f"Run {run} is not in the results file.")
        if start.get("source") != source:
            raise SittingError(
                f"Run {run} was made with {start.get('source')}; it cannot be resumed with "
                f"{source}."
            )
    return [start, *(r for r in rows if r.get("run") == start["run"] and r is not start)]


# The sitting ---------------------------------------------------------------------------------


def _say(text: str = "", *, end: str = "\n") -> None:
    print(text, end=end, flush=True)


@dataclass
class Sitting:
    """The steps of one run, start to summary. Everything it touches is handed in, so the
    tests script the keyboard, the clock and the launches."""

    steps: Sequence[Step]
    run_id: str
    source: str  # "athena" or "sim"
    versions: Mapping[str, str | None]
    ledger: Path
    launch: Callable[[Step], Ran]
    ask: Callable[[str], str]
    read_key: Callable[[], str | None]
    clock: Callable[[], float]
    sleep: Callable[[float], None]
    say: Say = _say
    judge: Callable[[Check, Path], Verdict] = judged
    pause: bool = False  # Enter before every check instead of the countdown
    settled: Mapping[str, Verdict] = field(default_factory=dict[str, Verdict])
    history: Sequence[Row] = ()  # the rows this run already has, when it is resumed
    rejudge_command: str = f"{COMMAND} --rejudge"
    released: float | None = None  # when the headband was last let go, as far as is known
    _outcomes: dict[str, str] = field(init=False, default_factory=dict[str, str])
    _attempts_made: Counter[str] = field(init=False, default_factory=Counter[str])
    _last: str = field(init=False, default="")
    _begun: bool = field(init=False, default=False)

    def run(self) -> int:
        """Run every step; 0 only when every requested check that can run here has passed."""
        requested: list[str] = (
            self.history[0]["checks"] if self.history else [s.id for s in self.steps]
        )
        if not self.history:
            start: Row = {"kind": "run", "checks": requested}
            h4 = next((s for s in self.steps if s.id == "H4"), None)
            if h4 is not None and h4.seconds != CHECKS["H4"].duration:
                start["h4_seconds"] = h4.seconds  # a rehearsal's shorter H4, for the report
            self._write(start)
        self._outcomes = standing(self.history, self.source)
        self._attempts_made = Counter(
            r["check"] for r in self.history if r.get("kind") == "attempt"
        )
        self._checklist()
        ended = False
        for step in self.steps:
            if ended:
                self._settle(step, Verdict(NOT_RUN, (ENDED,)))
            elif step.id in self.settled:
                self._settle(step, self.settled[step.id])
            elif (choice := self._before(step)) == "q":
                ended = True
                self._settle(step, Verdict(NOT_RUN, (ENDED,)))
            elif choice == "s":
                self._settle(step, Verdict(SKIPPED, ("skipped at the keyboard",)))
            else:
                ended = self._attempts(step)
        return self._summary(requested)

    # Before a step

    def _checklist(self) -> None:
        say = self.say
        say(f"Hardware acceptance, run {self.run_id} ({self.source}).")
        say(f"Verdicts are saved to {self.ledger}")
        say()
        say("On the desk before the start:")
        say("  - The headband is charged and switched on.")
        say("  - The Muse app on the phone is closed.")
        say("  - The PC is within 2 m of the headband for the whole sitting.")
        say("  - A dark cloth is within reach for F1 (cupped hands also work),")
        say("    and a lamp or a window to face.")
        say("  - This terminal window is focused. Do not click in it during the run.")
        say("    If text gets highlighted, press Esc.")
        say("  - Nothing else is recording from the headband.")
        say()
        minutes = sum(s.seconds + 25 for s in self.steps if s.id not in self.settled) / 60
        say(f"The plan, about {math.ceil(minutes)} min:")
        for step in self.steps:
            known = self.settled.get(step.id)
            note = f"  ({known.outcome}: {known.lines[0]})" if known else ""
            say(f"  {step.id:<6} {_mmss(step.seconds):>5}  {step.title}{note}")
        say()
        if self.pause:
            say("Every check waits for Enter.")
        else:
            say("After the first Enter each check starts by itself after a 10 s countdown.")
            say(self._keys_line("Any key during a countdown pauses it: p pause · s skip · q quit."))
        say("A FAIL always stops and waits.")
        say()

    def _explain(self, step: Step, *, full: bool) -> None:
        self.say(f"=== {step.id}: {step.title} · {_mmss(step.seconds)} ===")
        self.say(f"  {step.needs}")
        if full and step.check is not None:
            for line in step.check.before:
                self.say(f"  - {line}")
            self.say("  Cues on screen:")
            for at, text, _ in step.check.guide().timeline(-1.0):
                self.say(f"    {_mmss(at):>5}  {text}")

    def _before(self, step: Step) -> str:
        """How `step` may start: "" to go, "s" to skip it, "q" to end the run."""
        if self.pause or not self._begun:
            self._begun = True
            self._explain(step, full=True)
            return self.ask("Enter = start · s = skip · q = quit: ")
        return self._intermission(step)

    def _intermission(self, step: Step) -> str:
        while self.read_key() is not None:  # typed while nothing was listening
            pass
        if self._last:
            self.say(f"Last: {self._last}")
        self._explain(step, full=False)
        self.say("  " + self._keys_line("Any key pauses: p pause · s skip · q quit."))
        key = self._countdown(self.clock() + COOLDOWN_S, "Starts in", keys=True)
        if key is None or key in ("s", "q"):
            return key or ""
        self._explain(step, full=True)
        return self.ask("Paused. Enter = start · s = skip · q = quit: ")

    def _keys_line(self, keys: str) -> str:
        if self.source == "athena":
            return keys
        return "Rehearsal: the keys are played for you. Close the window to stop."

    def _countdown(self, until: float, label: str, *, keys: bool) -> str | None:
        """Count down to `until` on one line; with `keys`, the first key pressed ends it."""
        shown = -1
        key: str | None = None
        while key is None and (left := until - self.clock()) > 0:
            if keys and (key := self.read_key()) is not None:
                break
            if (whole := math.ceil(left)) != shown:
                shown = whole
                self.say(f"\r  {label} {whole:2d} s ", end="")
            self.sleep(min(0.2, left))
        if shown >= 0:
            self.say()
        return key

    # A step

    def _attempts(self, step: Step) -> bool:
        """Run `step` until it passes or the wearer moves on. True: they ended the run."""
        while True:
            verdict = self._attempt(step)
            self._settle(step, verdict)
            if verdict.outcome == PASS:
                return False
            choice = self.ask("r = retry · Enter = continue · q = quit: ")
            if choice != "r":
                return choice == "q"

    def _attempt(self, step: Step) -> Verdict:
        for tries in range(1, CONNECT_TRIES + 1):
            if self.released is not None:  # the headband is not ready sooner than this
                self._countdown(self.released + COOLDOWN_S, "Next connect in", keys=False)
            ran = self.launch(step)
            self.released = self.clock()
            if step.check is None or ran.code != EXIT_CONNECT or ran.session is not None:
                break
            if tries < CONNECT_TRIES:
                self.say(f"  No connection (try {tries} of {CONNECT_TRIES}). Is the headband")
                self.say("  switched on? Is the Muse app on the phone closed? Trying again.")
        else:
            hint = "Is the headband switched on? Is the Muse app on the phone closed?"
            return Verdict(NOT_RUN, (f"no connection in {CONNECT_TRIES} tries. {hint}",))
        if step.check is None:
            mark = "ok" if ran.code == 0 else "FAIL"
            line = f"[{mark}] its command exited with code {ran.code}"
            return Verdict(PASS if ran.code == 0 else FAIL, (*ran.lines, line), ran.measures)
        if ran.session is None:
            line = f"[FAIL] no session was saved (mufuse exited with code {ran.code})"
            return Verdict(FAIL, (line,))
        verdict = self.judge(step.check, ran.session)
        if ran.code != 0:  # the judges decide; the code is evidence
            note = f"[note] mufuse exited with code {ran.code}"
            verdict = replace(verdict, lines=(*verdict.lines, note))
        return verdict

    def _settle(self, step: Step, verdict: Verdict) -> None:
        """Save the attempt, then show it: a verdict on screen is already on disk."""
        self._attempts_made[step.id] += 1
        attempt = self._attempts_made[step.id]
        self._append_row("attempt", step.id, attempt, verdict)
        self._outcomes[step.id] = verdict.outcome
        self._last = f"{step.id} {verdict.outcome}"
        _show(self.say, step.id, verdict)
        if verdict.outcome == FAIL and verdict.session is not None:
            self.say(f"  Saved session: {verdict.session}")
            self.say("  To judge it again later, without the headband:")
            self.say(f'    {self.rejudge_command} "{verdict.session}"')
        self.say()

    def _append_row(self, kind: str, check_id: str, attempt: int, verdict: Verdict) -> None:
        row = _attempt_row(
            kind, self.run_id, self.clock(), check_id, attempt, verdict, self.source, self.versions
        )
        _append(self.ledger, row)

    def _write(self, fields: Row) -> None:
        row = {"run": self.run_id, "at": _iso(self.clock()), **fields, "source": self.source}
        _append(self.ledger, {**row, **self.versions})

    def _summary(self, requested: Sequence[str]) -> int:
        outcomes = {c: self._outcomes.get(c, NOT_RUN) for c in requested}
        passed = [c for c, o in outcomes.items() if o == PASS]
        # What was skipped before the start cannot run here at all (a rehearsal has no
        # headband for H1/H2): it is shown, and it is not held against the run.
        excused = [c for c in outcomes if c in self.settled and self.settled[c].outcome == SKIPPED]
        ok = len(passed) == len(outcomes) - len(excused)
        self._write({"kind": "summary", "outcomes": outcomes, "passed": ok})
        self.say(f"Summary of run {self.run_id} ({self.source})")
        for check_id, outcome in outcomes.items():
            self.say(f"  {check_id:<6} {outcome}")
        self.say(f"{len(passed)} of {len(outcomes)} passed.")
        for check_id in excused:
            self.say(f"{check_id} does not count here: {self.settled[check_id].lines[0]}.")
        if self.source != "athena":
            self.say("This ran on the simulator: it is not hardware evidence.")
        elif not ok:
            self.say(f"To run only what has not passed: {COMMAND} --resume {self.run_id}")
        write_report(self.ledger, self.run_id, self.say)
        return 0 if ok else 1


def _show(say: Say, check_id: str, verdict: Verdict) -> None:
    say()
    for line in verdict.lines:
        say(f"  {line}")
    say(f"  {check_id}: {verdict.outcome}")


def _iso(at: float) -> str:
    return datetime.fromtimestamp(at).isoformat(timespec="seconds")


def _mmss(seconds: float) -> str:
    s = round(seconds)
    return f"{s // 60}:{s % 60:02d}"


# Re-judge ------------------------------------------------------------------------------------

_NOTES = re.compile(r"(\S+) acceptance (\S+)")  # what the launcher writes into a session's notes


def _acceptance_session(folder: Path) -> tuple[str, str, str] | None:
    """(check id, run id, source) of a saved acceptance session; None for anything else."""
    try:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        found = _NOTES.fullmatch(manifest["notes"])
        driver = str(manifest["device"]["driver"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if found is None or found[1] not in CHECKS:
        return None
    # Only a BrainFlow recording is the headband; a simulated one stays "sim" for good.
    return found[1], found[2], "athena" if driver.startswith("brainflow") else "sim"


def rejudge(
    targets: Sequence[str],
    *,
    out: Path,
    ledger: Path,
    versions: Mapping[str, str | None],
    say: Say = _say,
    clock: Callable[[], float] = time.time,
    judge: Callable[[Check, Path], Verdict] = judged,
    h4_seconds: float | None = None,
) -> int:
    """Judge saved sessions again with the judges as they are now. Each target is a session
    folder (a path, or a name under `out`) or a run id, which stands for the last session of
    each of its checks. Rows are appended and marked; nothing already written is changed. A
    rehearsal's shorter H4 is taken from its run row unless `h4_seconds` says otherwise."""
    rows = read_rows(ledger)
    folders: list[Path] = []
    runs: list[str] = []  # the runs that got a row here, for their reports
    ok = True
    for target in targets:
        if Path(target).is_dir():
            folders.append(Path(target))
        elif (out / target).is_dir():
            folders.append(out / target)
        else:
            last = {
                r["check"]: r["session"]
                for r in rows
                if r.get("run") == target and r.get("kind") == "attempt" and r.get("session")
            }
            folders += [out / name for name in last.values()]
            if not last:
                ok = False
                say(f"{target}: neither a session folder nor a run with saved sessions.")
    for folder in folders:
        if not folder.is_dir():
            ok = False
            say(f"There is no session folder {folder.name} under {out}.")
            say("  Pass --out with the folder the run was recorded into.")
            continue
        found = _acceptance_session(folder)
        if found is None:
            ok = False
            say(f"{folder}: not an acceptance session.")
            continue
        check_id, run, source = found
        start = next((r for r in rows if r.get("kind") == "run" and r.get("run") == run), None)
        if source == "sim" and start is None:
            # A rehearsal keeps to its own log folder: its rows never go into another one.
            ok = False
            say(f"{folder.name} is from rehearsal {run}, which is not in {ledger}.")
            say("  Set MUFUSE_LOG_DIR to the log folder that rehearsal printed at its start.")
            continue
        check = CHECKS[check_id]
        short = h4_seconds if h4_seconds is not None else (start or {}).get("h4_seconds")
        if check_id == "H4" and short is not None and source == "sim":
            check = replace(check, duration=short)  # a rehearsal's H4; never the headband's
        verdict = judge(check, folder)
        attempt = next(
            (
                r.get("attempt")
                for r in reversed(rows)
                if r.get("kind") == "attempt"
                and r.get("run") == run
                and r.get("session") == folder.name
            ),
            None,
        )
        row = _attempt_row("rejudge", run, clock(), check_id, attempt, verdict, source, versions)
        _append(ledger, row)
        say(f"{folder.name} ({source}, run {run}), judged again:")
        _show(say, check_id, verdict)
        say()
        ok &= verdict.outcome == PASS
        if run not in runs:
            runs.append(run)
    for run in runs:
        write_report(ledger, run, say)
    return 0 if ok else 1


# Child processes -----------------------------------------------------------------------------


def _spawn(cmd: list[str], env: dict[str, str], cwd: Path | None) -> int:
    return subprocess.call(cmd, env=env, cwd=cwd)


@dataclass
class Launcher:
    """Starts a step as a child process and reports what it left behind."""

    exe: str  # the mufuse command
    repo: Path  # where scripts/ and tests/ are, for H3 and H1/H2
    out: Path
    run: str
    source: str  # "sim" also puts the simulated wearer of each check on the headband
    device: str | None
    env: Mapping[str, str]
    connect_log: Path
    spawn: Callable[[list[str], dict[str, str], Path | None], int] = _spawn

    def __call__(self, step: Step) -> Ran:
        if step.check is not None:
            return self._record(step.check)
        if step.id == "H3":
            return self._h3()
        cmd = [sys.executable, "-m", "pytest", "-m", "hardware", "-s"]
        return Ran(self.spawn(cmd, dict(self.env), self.repo))

    def _record(self, check: Check) -> Ran:
        self.out.mkdir(parents=True, exist_ok=True)
        before = set(self.out.iterdir())
        with tempfile.TemporaryDirectory() as tmp:
            guide_file = Path(tmp) / "guide.json"
            check.guide().save(guide_file)
            cmd = [self.exe, "record", "--source", self.source, "--duration", str(check.duration)]
            cmd += ["--notes", f"{check.id} acceptance {self.run}", "--out", str(self.out)]
            env = {
                **self.env,
                "MUFUSE_GUIDE": str(guide_file),
                "MUFUSE_RUN_LABEL": f"{check.id} {self.run}",
            }
            if self.source == "sim":
                env["MUFUSE_SIM_WEARER"] = check.id
            code = self.spawn(cmd + self._device(), env, None)
        return Ran(code, new_session(self.out, before))

    def _h3(self) -> Ran:
        """The ten-attempt script as it is. Its exit code is the verdict; what each attempt
        measured is copied from the connection log into the evidence."""
        earlier = len(read_runs(self.connect_log))
        script = self.repo / "scripts" / "h3_time_to_signal.py"
        cmd = [sys.executable, str(script), "--source", self.source, *self._device()]
        code = self.spawn(cmd, dict(self.env), None)
        new = read_runs(self.connect_log)[earlier:]
        runs = [r for r in new if (r.label or "").startswith("H3 ")]
        lines: list[str] = []
        times: list[float] = []
        for r in runs:
            took = r.outcome
            if r.seconds_to_signal is not None:
                times.append(r.seconds_to_signal)
                took = f"EEG after {r.seconds_to_signal:.1f} s"
            lines.append(f"{(r.label or '').rsplit(' ', 1)[-1]}: {took}")
        within = summarize(runs, H3_WITHIN_S, 0).passed
        lines.append(f"{within} of {len(runs)} attempts reached EEG within {H3_WITHIN_S:.0f} s")
        measures = {"h3.attempts": float(len(runs)), "h3.within_15_s": float(within)}
        if times:
            measures["h3.slowest_s"] = max(times)
        return Ran(code, None, tuple(lines), measures)

    def _device(self) -> list[str]:
        return ["--device", self.device] if self.device else []


# The keyboard and the command line -----------------------------------------------------------


def _read_key() -> str | None:
    if sys.platform == "win32":
        import msvcrt

        if msvcrt.kbhit():
            return msvcrt.getwch().lower()
    return None


def _ask(prompt: str) -> str:
    """One answer, lower case. Ctrl+C belongs to the recordings, so here it only asks again."""
    for _ in range(20):
        while _read_key() is not None:  # keys typed while nothing was listening
            pass
        try:
            return input(prompt).strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            if not sys.stdin.isatty():
                break
            print("  Ctrl+C does nothing here. Type q then Enter to quit.")
    return "q"


def _rehearsal_ask(prompt: str) -> str:
    _say(f"{prompt}(rehearsal: Enter)")
    return ""


def _selection_off(kernel32: Any = None) -> Callable[[], None]:
    """On a Windows console a click in the window starts a text selection (quick edit). While
    it lasts, everything written to the window waits and SPACE and Ctrl+C go to the selection.
    Switch it off for the run; the returned call puts it back. Where there is no such console
    (a pipe, another system) nothing is changed. Terminals that select by themselves still do:
    there Esc ends a selection."""
    if kernel32 is None:
        if sys.platform != "win32":
            return lambda: None
        kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-10)  # the console's input
    mode = ctypes.c_uint32()
    if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        return lambda: None
    before = mode.value
    # 0x0040 is quick edit; 0x0080 (extended flags) is what makes the console take the change.
    kernel32.SetConsoleMode(handle, (before & ~0x0040) | 0x0080)
    return lambda: kernel32.SetConsoleMode(handle, before)


def _ignore(signum: int, frame: object) -> None:
    """Ctrl+C reaches the recording, which stops and saves; the runner carries on."""


def main(
    argv: Sequence[str] | None = None,
    *,
    repo: Path,
    spawn: Callable[[list[str], dict[str, str], Path | None], int] = _spawn,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """`repo` is the checkout the launcher script lives in: H3's script and the hardware tests
    are run from there."""
    use_utf8_output()
    ap = argparse.ArgumentParser(
        prog="hw_acceptance.py", description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    ap.add_argument("checks", nargs="*", help="a subset, e.g. H5 F1 (default: the whole sitting)")
    ap.add_argument("--device", help="headband name, e.g. MuseS-1A2B")
    ap.add_argument("--out", type=Path, help="where sessions are saved (default: recordings)")
    ap.add_argument("--pause", action="store_true", help="wait for Enter before every check")
    ap.add_argument("--no-h3", action="store_true", help="leave out the ten connects of H3")
    ap.add_argument(
        "--resume",
        nargs="?",
        const="",
        metavar="RUN",
        help="run only what RUN has not passed (default: the latest run on the headband)",
    )
    ap.add_argument(
        "--rejudge",
        nargs="+",
        metavar="RUN_OR_FOLDER",
        help="judge saved sessions again, without the headband",
    )
    ap.add_argument(
        "--rehearse",
        action="store_true",
        help="the whole sitting on the simulator, unattended, into scratch folders",
    )
    ap.add_argument("--h4-seconds", type=float, help="a shorter H4, for a rehearsal only")
    args = ap.parse_args(argv)
    previous = signal.signal(signal.SIGINT, _ignore)  # Ctrl+C belongs to the recording
    selection_back = _selection_off()
    try:
        return _main(args, repo, spawn, clock, sleep)
    except SittingError as exc:
        _say(str(exc))
        return 2
    finally:
        selection_back()
        signal.signal(signal.SIGINT, previous)


def _main(
    args: argparse.Namespace,
    repo: Path,
    spawn: Callable[[list[str], dict[str, str], Path | None], int],
    clock: Callable[[], float],
    sleep: Callable[[float], None],
) -> int:
    h4_seconds: float | None = args.h4_seconds
    rehearse: bool = args.rehearse
    if h4_seconds is not None and not (rehearse or args.rejudge):
        raise SittingError("--h4-seconds is for a rehearsal: on the headband H4 is ten minutes.")
    if args.rejudge:
        ledger = log_path().with_name("acceptance.jsonl")
        out: Path = args.out or Path("recordings")
        return rejudge(
            args.rejudge, out=out, ledger=ledger, versions=versions(repo), h4_seconds=h4_seconds
        )
    # On PATH, or beside this interpreter: a virtual environment that was not activated.
    beside = Path(sys.executable).with_name("mufuse.exe" if sys.platform == "win32" else "mufuse")
    exe = shutil.which("mufuse") or (str(beside) if beside.is_file() else None)
    if exe is None:
        raise SittingError(f"mufuse is not on PATH; run this with `{COMMAND}`.")

    env = {k: v for k, v in os.environ.items() if k not in _OWN_ENV} | {"PYTHONUTF8": "1"}
    logs = log_path().parent
    out = args.out or Path("recordings")
    if rehearse and not (args.out and "MUFUSE_LOG_DIR" in os.environ):
        if args.resume is not None:
            raise SittingError(
                "A rehearsal can only be resumed where it ran: set MUFUSE_LOG_DIR and pass --out "
                "as that rehearsal printed them at its start."
            )
        # Never into the real log or the real recordings: a scratch folder for what was not given.
        scratch = Path(tempfile.mkdtemp(prefix="mufuse-rehearsal-"))
        logs = Path(os.environ.get("MUFUSE_LOG_DIR") or scratch / "logs")
        out = args.out or scratch / "sessions"
        env["MUFUSE_LOG_DIR"] = str(logs)
    ledger = logs / "acceptance.jsonl"
    source = "sim" if rehearse else "athena"

    history: list[Row] = []
    if args.resume is not None:
        if args.checks or args.no_h3:
            raise SittingError("--resume takes its checks from the run: name none with it.")
        history = to_resume(read_rows(ledger), args.resume or None, source)
        run: str = history[0]["run"]
        if h4_seconds is None:
            h4_seconds = history[0].get("h4_seconds")  # a rehearsal's shorter H4 stays as it was
        left = [c for c in history[0]["checks"] if standing(history, source).get(c) != PASS]
        if not left:
            _say(f"Every check of run {run} has passed.")
            return 0
        steps = plan(left, h4_seconds=h4_seconds)
    else:
        run = datetime.fromtimestamp(clock()).strftime("%Y%m%d-%H%M%S")
        steps = plan(args.checks, h3=not args.no_h3, h4_seconds=h4_seconds)

    short_h4 = "" if h4_seconds is None else f" --h4-seconds {h4_seconds:g}"
    sitting = Sitting(
        steps,
        run_id=run,
        source=source,
        versions=versions(repo),
        ledger=ledger,
        launch=Launcher(
            exe, repo, out, run, source, args.device, env, logs / "connect.jsonl", spawn
        ),
        ask=_rehearsal_ask if rehearse else _ask,
        read_key=(lambda: None) if rehearse else _read_key,
        clock=clock,
        sleep=sleep,
        pause=args.pause,
        settled=settled(steps, rehearse=rehearse),
        history=history,
        rejudge_command=f"{COMMAND}{short_h4} --rejudge",
        # A run begun right after another one waits like any next check does.
        released=None if rehearse else last_release(logs / "connect.jsonl"),
    )
    _say(f"Sessions are saved to {out}")
    if rehearse:
        _say(f"To resume this rehearsal or judge it again later, set MUFUSE_LOG_DIR to {logs}")
        _say(f"and pass --out {out}")
    return sitting.run()


# Set per child by the launchers; a value left in the shell must not leak into a check.
_OWN_ENV = ("MUFUSE_GUIDE", "MUFUSE_RUN_LABEL", "MUFUSE_SIM_WEARER", "MUFUSE_T0")
