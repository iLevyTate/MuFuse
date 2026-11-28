# Hardware acceptance: 001 acquisition

Every hardware check of feature 001 runs in one sitting, from one command:

```
uv run python scripts/hw_acceptance.py
```

It takes about 27 minutes. The first 9 need hands; the rest runs by itself. Every verdict is saved
before it is shown and every recording stays on disk, so a check that fails can be judged again
later without the headband.

Rehearse it once before the real sitting. This plays the whole run on the simulator, unattended,
and touches neither the headband nor the real logs:

```
uv run python scripts/hw_acceptance.py --rehearse --h4-seconds 30
```

## Known issue: the ear sensors

The ear sensors (TP9, TP10) do not hold contact reliably (issue #12). While one of them is
out, P0 fails and H8 cannot be judged; both passed once on 2026-11-27 after the sensors were
wiped, and every other check has passed. P0 is not loosened.
Numbers, what is affected and what to try: `docs/KNOWN-ISSUES.md`. The checks that do not need
ear contact run with:

```
uv run python scripts/hw_acceptance.py H6 H7 H5 F1 H4
```

## On the desk before the start

- The headband is charged (P0 wants 20% or more) and switched on.
- The Muse app on the phone is closed. Only one device can connect to the headband.
- The PC is within 2 m of the headband for the whole sitting.
- A dark cloth is within reach for F1 (cupped hands also work), and a lamp or a window to face.
- A Windows terminal, focused. Do not click in it during the run: SPACE and Ctrl+C only register
  in the focused window, and a click can start a text selection that holds the output and takes
  the keys. If text gets highlighted, press Esc. The run switches click-to-select off where the
  console allows it. H6 reads SPACE on Windows only; elsewhere it ends as NOT RUN.
- Nothing else is recording from the headband.

## Order and timeline

The checks that need hands come first, the headband comes off in F1, and the hands-free ones are
last. Times are from the first Enter and allow about 25 s between checks for the countdown and
the verdict.

| Starts at | Check | Length | Hands |
|---|---|---|---|
| 0:00 | P0 Preflight: fit, battery and streams | 0:45 | adjust the fit, then rest |
| 1:10 | H8 Channel check reacts to contact, jaw and blinks | 1:03 | one hand at the left ear sensor |
| 2:40 | H6 Keyboard markers (SC-004) | 0:40 | one finger over SPACE |
| 3:45 | H7 Ctrl+C leaves a readable session (SC-005) | 1:00 at most | Ctrl+C once |
| 5:10 | H5 Power-cycle recovery (SC-003) | 1:15 | the headband's power button |
| 6:50 | F1 fNIRS optics: which channels are ambient light | 1:38 | headband off, cloth |
| 8:55 | H4 10-minute completeness (SC-002) | 10:00 | none |
| 19:20 | H3 Time to first signal, 10 connects (SC-001) | 5:00 | none |
| 24:45 | H1/H2 Discovery and 30 s of every stream | 1:00 | none |

## What each check asks, and what passes

During a recording an orange bar under the live table shows the current instruction and a
countdown. Every action gets a 3-second "get ready" first, and the pass rules allow for reaction
time. Cue times, lengths and pass rules live in `src/mufuse/acceptance.py`, so every run is the
same.

| Check | What the wearer does | Passes when |
|---|---|---|
| P0 | Adjust the headband for 15 s until all four sensors are good (green in the live view), then sit still for 30 s, eyes open, jaw relaxed. | Battery ≥ 20%; every stream ≥ 95% of its nominal rate; while still, each EEG channel reads ok in ≥ 80% of windows and its quietest windows stay ≤ 75 µV. |
| H8 | Sit still 15 s. Lift the LEFT ear sensor (TP9) off the skin for 10 s, let it back. Clench the jaw for 8 s, relax. Blink about once a second for 10 s. | Against the same recording's rest: the lift changes TP9 in ≥ 50% of windows and TP9 was steady at rest; the clench raises the std ≥ 3 times on TP9 or TP10; no channel goes flat or railed while blinking. The number of blinks is reported, not judged. |
| H6 | Press SPACE once at each of three cues (0:10, 0:18, 0:26). | Each cue has a SPACE marker from 3 s before to 5 s after it. Extra presses are reported, not counted. |
| H7 | Tap Ctrl+C once at the cue (0:15). Do not hold it. | The session reloads as finalized, with EEG samples, and stopped from 3 s before to 10 s after the cue. |
| H5 | Turn the headband OFF at the cue (0:20), keep it off about 10 s, turn it ON at the cue (0:30). Press nothing while it reconnects; the screen may stand still for up to 15 s. | The signal stops from 3 s before to 8 s after the power-off cue and is away ≥ 8 s; streaming is back ≤ 20 s after the power-on cue (+3 s tolerance); the recorded gap matches the hole in the EEG data within ±0.5 s. |
| F1 | Sit still 30 s. Take the headband off and hold the forehead sensors towards the light for 25 s. Cover them completely for 25 s. Uncover them for 15 s. Keep it switched on. | OPT5 to OPT8 (BrainFlow wire order) all behave as ambient light, and none of OPT11, 12, 15, 16 (the other known order) does. A row behaves as ambient light when it reads the same covered as on the head (within 10%) and ≥ 1000 counts more in room light. Any other row that does so is reported, not judged. |
| H4 | Nothing. The headband is worn or lies switched on within 2 m. Leave the keyboard alone. | At least 9:50 recorded, and every stream ≥ 99.5% complete. |
| H3 | Nothing. It connects ten times by itself (`scripts/h3_time_to_signal.py`). `--no-h3` leaves it out. | EEG within 15 s of the command start in ≥ 9 of 10 connects. |
| H1/H2 | Nothing. The hardware tests run by themselves (`pytest -m hardware -s`). | The headband is found, and each stream delivers ≥ 95% of its nominal samples over 30 s. |

SC-003 asks for the gap to be *recorded accurately*, not for the headband to be off for exactly
10 s: the gap also includes boot and reconnect time, so H5 compares the recorded gap with the hole
in the EEG data. Its verdict lists every step of the reconnect with its time (signal counted as
lost, old connection let go, each attempt, connected, first sample), so a FAIL shows which step
used the time.

Two things are said first in any verdict, before the check's own rules: that the recording was
stopped by `q` or Ctrl+C before its time (every check but H7, which asks for the stop), and that
no sample was recorded at all. Both mean "run it again", not that the cues were missed.

## Pause, skip, retry

- The run shows the desk checklist and the plan, then waits for one Enter.
- Every recording says when it is connecting (usually about 5 s) and when it is letting go of the
  headband (about 8 s). Nothing is pressed during either.
- A run begun within about 20 s of the last one counts down first: the headband needs that long
  after a release.
- After that each check starts by itself after a 10 s countdown that shows the last verdict and
  what the next check needs. The countdown is also the pause the headband needs between a release
  and the next connect.
- Any key during a countdown pauses it: `p` pause, `s` skip this check, `q` quit the run.
  `--pause` waits for Enter before every check instead.
- A FAIL always stops and waits: `r` runs the check again, Enter goes on, `q` quits. The last
  attempt of a check counts.
- No connection after three tries ends the check as NOT RUN with a hint, and waits.
- Ctrl+C only stops the recording that is running (H7 asks for it). It never ends the run.

Every check ends as PASS, FAIL, SKIPPED or NOT RUN. The exit code is 0 only when every requested
check has passed. A rehearsal cannot run H1/H2 and shows it as SKIPPED; that alone does not make
its exit code 1.

## The other ways to run it

```
uv run python scripts/hw_acceptance.py H5 F1           # just these, in the sitting order
uv run python scripts/hw_acceptance.py --resume        # only what the last headband run has not passed
uv run python scripts/hw_acceptance.py --resume RUN    # the same for a run id
uv run python scripts/hw_acceptance.py --rejudge RUN   # judge a run's saved sessions again
uv run python scripts/hw_acceptance.py --rejudge recordings/<session>   # or one session
uv run python scripts/hw_acceptance.py --rehearse      # the whole sitting on the simulator
```

- `--resume` keeps the run id, so the report and the results file still describe one sitting.
- `--rejudge` needs no headband. It runs the judges as they are now over what was saved and
  prints every rule with its numbers. The new verdict is appended as its own row, nothing is
  overwritten, and the report is written again. Use it after a FAIL, and after any change to a
  judge or to `signal_check.py`.
- `--rehearse` plays the sitting in real time with a simulated wearer on the headband and the
  keys. It never writes to the real logs or to `recordings/`: unless both `--out` and
  `MUFUSE_LOG_DIR` are given, it keeps to a scratch folder of its own and prints where.
  `--h4-seconds 30` shortens H4 for it; `--resume` and `--rejudge` take that length from the
  run. Both only work on a rehearsal where it ran: set `MUFUSE_LOG_DIR` and pass `--out` as the
  rehearsal printed them at its start. Its rows are marked `sim`, its report says SIMULATOR
  REHEARSAL at the top, and it never counts as hardware evidence.

## Where things are saved

| What | Where | In it |
|---|---|---|
| Results file | `acceptance.jsonl` in the log folder | One row per run start, attempt, re-judgement and summary: outcome, the judge's lines, the measures, firmware, versions and commit. |
| Report | `acceptance/<run id>/report.md` in the log folder | The run in one page: facts, the table of checks, calibration tables and suggestions, how to reproduce. |
| Connection log | `connect.jsonl` in the log folder | Every `stream`/`record` attempt with its time to first EEG, outcome and error. H3 reads its verdict from here. |
| Sessions | `recordings/` in the repository (git-ignored), or `--out` | One folder per recording, with notes like `H5 acceptance <run id>`. Besides the samples, markers and gaps it holds `reconnects.jsonl`: the steps of every reconnect with their times. |

The log folder is `%LOCALAPPDATA%\mufuse\Logs` on Windows (`MUFUSE_LOG_DIR` overrides it). It is
outside the repository. The run prints the path of the results file at the start and of the
report at the end.

## What goes into the pull request, and what never does

Paste the text of `report.md`. It is built from an allowlist: run id, date, source, versions and
commit, OS, preset, firmware, battery, the outcome and key numbers of each check, the calibration
tables and the commands to reproduce. The headband's name is masked (`MuseS-****`). It holds no
paths, no user name, no Bluetooth address, no samples and no notes.

Never share, and never commit:

- anything under `recordings/`: the sessions are raw signals from a person's head;
- `acceptance.jsonl` and `connect.jsonl`: they hold session names, the headband's name and
  error text that can contain paths;
- screenshots or copies of the terminal: it prints the full paths of the sessions and the logs.

The report of a rehearsal is not hardware evidence and says so in its first lines.

## Calibration

The report ends with per-channel tables from P0, H8, H4 and F1 and with suggested thresholds for
the live channel check, for example a noisy threshold at the geometric midpoint between the spread
at rest and the spread with the jaw clenched, or "not separable" when the two overlap. They are
suggestions only. Nothing in a run changes `src/mufuse/acquisition/signal_check.py`: that is tuned
in feature 002, in a reviewed commit that cites the run id and is checked with `--rejudge`.

# Hardware sitting: 002 signal quality

One guided session of 9.5 minutes, from one command. The Muse app must be closed.

```
uv run mufuse quality label --source athena
```

It starts with a pre-flight check: fit the headband until AF7 and AF8 (forehead) read good; the
session then starts by itself. If they are not good after 60 s, press `s` to start anyway or `q` to
stop. The ear sensors are only noted (issue #12). What was out is printed and kept in the recording.
The end of eyes-closed is a tone from the sound card (Windows, macOS, Linux), not only the terminal
bell: check your volume. Then the screen tells you each step and counts it ("Blink 7 of 20"):

| Time | Block |
|---|---|
| 0:00 | Settle: sit still, check the sensor panel |
| 0:20 | Sit still, eyes open (1 minute) |
| 1:20 | Sit still, eyes closed until the bell (1 minute) |
| 2:30 | 20 blinks, one at each cue |
| 4:00 | 20 jaw clenches of about 1 s |
| 5:50 | 20 head turns, to one side and back |
| 7:40 | 10 lifts of a forehead sensor (AF7, AF8 in turn) for 5 s each |
| 9:25 | Done: it saves, scores and checks that replaying the recording gives the same answers |

The recording goes to `recordings/` (never committed). To score it again later, or after the
limits change:

```
uv run mufuse quality score recordings/<session>
uv run mufuse inspect recordings/<session>
```

Rehearse it first without the headband (the simulator follows every cue; it takes the same
9.5 minutes):

```
uv run mufuse quality label --source sim --out <a scratch folder>
```

The ear sensors are not needed: everything in this session reads AF7, AF8 and the motion sensors.

