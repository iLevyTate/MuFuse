"""H3 / SC-001: time from command to live EEG, repeated, logged and judged.

Runs `mufuse stream` N times (default 10). Each attempt streams for --hold seconds after it
connects, then the headband gets --cooldown seconds to release Bluetooth before the next one.
Every attempt lands in the connection log (`mufuse.runlog.log_path()`) tagged with this run's id.

    uv run python scripts/h3_time_to_signal.py
    uv run python scripts/h3_time_to_signal.py --attempts 10 --hold 10 --cooldown 10
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime

from mufuse.runlog import ConnectRun, append_run, log_path, read_runs, summarize


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--attempts", type=int, default=10)
    ap.add_argument("--hold", type=float, default=10.0, help="seconds to stream once connected")
    ap.add_argument("--cooldown", type=float, default=10.0, help="seconds between attempts")
    ap.add_argument("--threshold", type=float, default=15.0, help="pass if EEG within N s")
    ap.add_argument("--need", type=int, default=9, help="attempts that must pass")
    ap.add_argument("--timeout", type=float, default=60.0, help="kill a hung attempt after N s")
    ap.add_argument("--device", help="headband name, e.g. MuseS-1A2B")
    ap.add_argument("--source", default="athena", help="sim to dry-run without the headband")
    args = ap.parse_args()

    exe = shutil.which("mufuse")
    if exe is None:
        print("mufuse not on PATH; run this with `uv run python scripts/h3_time_to_signal.py`.")
        return 2
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    cmd = [exe, "stream", "--source", args.source, "--duration", str(args.hold)]
    if args.device:
        cmd += ["--device", args.device]
    print(f"H3 run {run_id}: {args.attempts} attempts, log {log_path()}\n")

    try:
        for i in range(1, args.attempts + 1):
            _attempt(cmd, args, f"H3 {run_id} {i}/{args.attempts}")
            if i < args.attempts:
                _countdown(args.cooldown)
    except KeyboardInterrupt:
        print("\nStopped early.")

    runs = [r for r in read_runs() if r.label and r.label.startswith(f"H3 {run_id} ")]
    print(f"\nH3 run {run_id}")
    for r in runs:
        took = f"{r.seconds_to_signal:5.1f} s" if r.seconds_to_signal is not None else "    —  "
        fast = r.seconds_to_signal is not None and r.seconds_to_signal <= args.threshold
        detail = f"  {r.error}" if r.error else ""
        attempt = r.label.rsplit(" ", 1)[-1]
        print(f"  {attempt:>5}  {took}  {r.outcome:<13} {'pass' if fast else 'FAIL'}{detail}")
    summary = summarize(runs, args.threshold, args.need)
    verdict = "PASS" if summary.ok and summary.attempts >= args.attempts else "FAIL"
    print(
        f"\n{summary.passed}/{summary.attempts} reached EEG within {args.threshold:.0f} s "
        f"(need {args.need}/{args.attempts}): {verdict}"
    )
    return 0 if verdict == "PASS" else 1


def _attempt(cmd: list[str], args: argparse.Namespace, label: str) -> None:
    print(f"--- attempt {label.rsplit(' ', 1)[-1]} ---", flush=True)
    t0 = time.time()
    env = {**os.environ, "MUFUSE_T0": repr(t0), "MUFUSE_RUN_LABEL": label}
    try:
        subprocess.run(cmd, env=env, timeout=args.hold + args.timeout, check=False)
    except subprocess.TimeoutExpired:
        append_run(
            ConnectRun(
                at=datetime.fromtimestamp(t0).isoformat(timespec="seconds"),
                command="stream",
                source=args.source,
                device=args.device,
                preset="p1041",
                outcome="timeout",
                seconds_to_signal=None,
                elapsed_s=round(time.time() - t0, 3),
                error=f"no exit after {args.hold + args.timeout:.0f} s; killed",
                label=label,
            )
        )
        print("attempt hung and was killed", flush=True)


def _countdown(seconds: float) -> None:
    end = time.time() + seconds
    while (left := end - time.time()) > 0:
        print(f"\rcooldown {left:4.1f} s ", end="", flush=True)
        time.sleep(min(0.2, left))
    print("\r" + " " * 20 + "\r", end="", flush=True)


if __name__ == "__main__":
    sys.exit(main())
