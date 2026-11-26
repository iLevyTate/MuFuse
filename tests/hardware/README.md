# Hardware acceptance checklist: 001 acquisition

Run with the headband on, the Muse app closed, and the PC within 2 m. Record results in the PR.

| # | Check | How | Pass |
|---|---|---|---|
| H1 | Discovery (T016) | `uv run pytest -m hardware -s -k discoverable` | Headband listed |
| H2 | All streams (T017) | `uv run pytest -m hardware -s -k streams` | Each stream ≥ 95% of nominal samples over 30 s |
| H3 | SC-001 time to signal | `uv run python scripts/h3_time_to_signal.py` (10 attempts, 10 s each, 10 s apart; logged) | ≤ 15 s in ≥ 9/10 |
| H4 | SC-002 completeness | Guided: sit still for 10 min | Every stream ≥ 99.5% complete |
| H5 | SC-003 dropout recovery | Guided: power off at 0:20, on at 0:30 | Streaming resumes ≤ 20 s after power-on; recorded gap matches the hole in the data ±0.5 s |
| H6 | SC-004 markers | Guided: press SPACE at 0:10, 0:18, 0:26 | 3 keyboard markers, each near its cue |
| H7 | SC-005 interruption | Guided: Ctrl+C at 0:15 | Session reloads as finalized, stopped by Ctrl+C |
| H8 | Channel check sanity | Guided: rest, lift left ear sensor, clench, blink | Lifted → `flat`/`railed`; clench → `noisy` on TP9/TP10; blinks stay `ok` |
| F1 | fNIRS optics: ambient channels | Guided: on head, then off facing room light, covered, uncovered | Darkness hits OPT5–8 hardest (BrainFlow wire order); info: least pulse on the head |

H8 is how to tune the thresholds in `src/mufuse/acquisition/signal_check.py`; its report prints each
channel's robust spread in µV per phase.

## One sitting (all of it)

```
uv run python scripts/hw_acceptance.py                 # the whole sitting, about 30 min
uv run python scripts/hw_acceptance.py H5 F1           # just these
uv run python scripts/hw_acceptance.py --resume        # only what the last run did not pass
uv run python scripts/hw_acceptance.py --rejudge RUN   # judge saved sessions again, no headband
uv run python scripts/hw_acceptance.py --rehearse      # the whole sitting on the simulator
```

Order: P0 (fit), H8, H6, H7, H5, F1 need hands and come first; the headband comes off in F1. Then
H4 (10 min, worn or on the desk within 2 m), H3 (the ten connects of `h3_time_to_signal.py`;
`--no-h3` leaves it out) and H1/H2 (`pytest -m hardware -s`) need nothing.

The run shows a desk checklist and waits for one Enter. After that each check starts by itself after
a 10 s countdown that shows the last verdict and what the next check needs. Any key pauses the
countdown (`p` pause, `s` skip, `q` quit); `--pause` waits for Enter before every check instead. The
countdown is also the pause the headband needs between a release and the next connect. A FAIL always
stops and waits: `r` runs the check again, Enter goes on. Ctrl+C only stops the recording that is
running (H7 asks for it), never the run.

During a recording an orange bar under the live table shows the current instruction and a countdown;
every action ("turn the headband OFF", "press SPACE") gets a 3-second "get ready" countdown first,
and the pass rules allow for reaction time. Cue times, durations and pass rules live in
`src/mufuse/acceptance.py`, so every run is the same.

Every check ends as PASS, FAIL, SKIPPED or NOT RUN (no connection after three tries, or the run was
ended first), and the exit code is 0 only when all of them passed. Each attempt is one row in
`acceptance.jsonl` next to the connection log, saved before its verdict is shown, with the run id,
the measures, the firmware, the package versions and the commit. Sessions are saved under
`recordings/` with notes like `H5 acceptance <run id>`, so a FAIL can be judged again later with
`--rejudge` (a run id, or session folders); a re-judgement is appended as its own row and nothing is
overwritten. The last row of a check counts.

`--rehearse` plays the whole sitting in real time on the simulator, with a simulated wearer on the
headband and the keys, into scratch folders (`--out` and `MUFUSE_LOG_DIR` choose them). Its rows are
marked `sim` and never count as hardware evidence; `--h4-seconds 30` shortens H4 for it.

SC-003 asks for the gap to be *recorded accurately*, not for the headband to be off for exactly
10 s: the gap also includes boot and reconnect time, so H5 compares the recorded gap with the hole
in the EEG data.

Every `stream`/`record` attempt is appended to the connection log (`connect.jsonl` in the user log
folder, e.g. `%LOCALAPPDATA%\mufuse\Logs` on Windows) with its time to first EEG, outcome and any
error. The H3 script tags its attempts with a run id and prints the verdict from that log.
