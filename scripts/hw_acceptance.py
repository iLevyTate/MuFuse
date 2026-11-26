"""Guided hardware acceptance: H4-H8 for 001, then F1 (fNIRS optics), with cues and verdicts.

Each check explains what you'll do, waits for Enter, then runs `mufuse record` with timed cues in
the live view (every action gets a 3-second "get ready" countdown). When the recording ends, the
session is checked against the pass rules in `mufuse.acceptance`, and the verdict is appended to
`acceptance.jsonl` next to the connection log.

    uv run python scripts/hw_acceptance.py             # H4 H5 H6 H7 H8 F1
    uv run python scripts/hw_acceptance.py H5 H8       # just these
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from mufuse.acceptance import CHECKS, Check, Result
from mufuse.recording.reader import load_session
from mufuse.runlog import log_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("checks", nargs="*", default=list(CHECKS), help="e.g. H5 F1")
    ap.add_argument("--device", help="headband name, e.g. MuseS-C27F")
    ap.add_argument("--source", default="athena", help="sim to dry-run without the headband")
    ap.add_argument("--out", type=Path, default=Path("recordings"))
    args = ap.parse_args()
    unknown = [c for c in args.checks if c.upper() not in CHECKS]
    if unknown:
        print(f"Unknown check(s): {', '.join(unknown)}. Choose from {', '.join(CHECKS)}.")
        return 2
    exe = shutil.which("mufuse")
    if exe is None:
        print("mufuse not on PATH; run this with `uv run python scripts/hw_acceptance.py`.")
        return 2

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    results_path = log_path().parent / "acceptance.jsonl"
    print(f"Acceptance run {run_id}. Results go to {results_path}")
    print("Close the Muse phone app and keep the headband on unless a step says otherwise.\n")

    results: list[Result] = []
    for check_id in (c.upper() for c in args.checks):
        check = CHECKS[check_id]
        while True:
            _explain(check)
            choice = _ask("Enter = start · s = skip · q = quit: ")
            if choice == "q":
                return _summary(results)
            if choice == "s":
                break
            result, session_dir = _run(check, exe, args, run_id)
            _show(result)
            _save(results_path, run_id, result, session_dir)
            if result.passed or _ask("r = retry · Enter = continue: ") != "r":
                results.append(result)
                break
    return _summary(results)


def _explain(check: Check) -> None:
    print(f"=== {check.id}: {check.title} · {_mmss(check.duration)} ===")
    for line in check.before:
        print(f"  - {line}")
    print("  Cues on screen:")
    for at, text, _ in check.guide().timeline(-1.0):
        print(f"    {_mmss(at):>5}  {text}")


def _run(
    check: Check, exe: str, args: argparse.Namespace, run_id: str
) -> tuple[Result, Path | None]:
    args.out.mkdir(parents=True, exist_ok=True)
    before = set(args.out.iterdir())
    with tempfile.TemporaryDirectory() as tmp:
        guide_file = Path(tmp) / "guide.json"
        check.guide().save(guide_file)
        cmd = [exe, "record", "--source", args.source, "--duration", str(check.duration)]
        cmd += ["--notes", f"{check.id} acceptance {run_id}", "--out", str(args.out)]
        if args.device:
            cmd += ["--device", args.device]
        env = {
            **os.environ,
            "MUFUSE_GUIDE": str(guide_file),
            "MUFUSE_RUN_LABEL": f"{check.id} {run_id}",
        }
        proc = subprocess.Popen(cmd, env=env)
        while True:
            try:
                code = proc.wait()
                break
            except KeyboardInterrupt:
                continue  # H7's Ctrl+C is for the recording, not for this script
    new = sorted(set(args.out.iterdir()) - before)
    if not new:
        lines = (f"[FAIL] no session was saved (mufuse exited with code {code})",)
        return Result(check.id, False, lines), None
    return check.evaluate(load_session(new[-1])), new[-1]


def _show(result: Result) -> None:
    print()
    for line in result.lines:
        print(f"  {line}")
    print(f"  {result.check}: {'PASS' if result.passed else 'FAIL'}\n")


def _save(path: Path, run_id: str, result: Result, session_dir: Path | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "run": run_id,
        "at": datetime.now().isoformat(timespec="seconds"),
        "check": result.check,
        "passed": result.passed,
        "lines": list(result.lines),
        "session": str(session_dir) if session_dir else None,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def _summary(results: list[Result]) -> int:
    if results:
        print(
            "Summary: " + "  ".join(f"{r.check} {'PASS' if r.passed else 'FAIL'}" for r in results)
        )
    return 0 if results and all(r.passed for r in results) else 1


def _ask(prompt: str) -> str:
    try:
        return input(prompt).strip().lower()
    except (KeyboardInterrupt, EOFError):
        print()
        return "q"


def _mmss(seconds: float) -> str:
    s = round(seconds)
    return f"{s // 60}:{s % 60:02d}"


if __name__ == "__main__":
    sys.exit(main())
