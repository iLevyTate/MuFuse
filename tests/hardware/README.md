# Hardware acceptance test: feature 001

The acceptance test is guided. One command walks you through every check: it tells you what
to do and when, measures the results, grades them against the spec and writes a report to
paste into the pull request.

## Before you start

- Charge the headband. The full run takes about 15 minutes, including a 10-minute recording.
- Close the Muse app on your phone (or turn the phone's Bluetooth off). The headband connects
  to one device at a time.
- Sit within 2 m of the computer.
- Update the code: `git pull`, then `uv sync`.

## Run it

```bash
uv run mufuse hardware-test --dry-run --quick   # optional preview: simulated headband, a few minutes
uv run mufuse hardware-test                     # the real test, about 15 minutes
```

Each step explains itself and waits for Enter. When a highlighted `▶` direction appears (with a
terminal beep), do it straight away. Ctrl+C stops the run at any time; checks that already
finished are still saved in the report.

## The steps

| Step | What you do | What it checks | Passes when |
|---|---|---|---|
| 1. Find the headband | Press Enter | Bluetooth scan (FR-001) | The headband is listed |
| 2. Read the firmware version | Nothing | Firmware query over Bluetooth (T025) | A version is read; it is saved in every test recording |
| 3. Every sensor streams | Sit still for 30 s | EEG, motion and optics rates (FR-002) | Each stream delivers ≥ 95% of its nominal rate |
| 4. Time to live signal | Nothing; it connects 10 times | SC-001 | Live EEG within 15 s in ≥ 9 of 10 attempts |
| 5. Sensor contact check | Rest, blink, clench your jaw, lift the sensor behind your left ear | The live contact indicator | Rest and blinks read `ok`; clench reads `noisy` on TP9/TP10; lifted TP9 reads `flat` or `railed` |
| 6. 10-minute recording with markers | Sit; press SPACE 3 times when asked | SC-002 and SC-004 | Every stream ≥ 99.5% complete; 3 markers, each within one EEG sample (3.9 ms) of the data |
| 7. Recovers after power-off | Switch the headband off when told, then back on when told | SC-003 | Streaming resumes ≤ 20 s after the power-on prompt; one gap recorded, within ±0.5 s of the measured outage |
| 8. Ctrl+C leaves a readable recording | Press Ctrl+C once when told | SC-005 | The recording reloads as finalized |

Step 5 also records, for each sensor and condition, how the indicator classified the signal and
how large the signal was. That table in the report is what we use to tune the thresholds in
`src/mufuse/acquisition/signal_check.py`. A failure there means the thresholds need tuning, not
that acquisition is broken.

## After the run

The command prints where it saved everything:

```
recordings/hardware-tests/<run id>/
  report.md      paste this into the feature 001 pull request
  report.json    the same results with every measured number
  sessions/      the three test recordings (inspect them with `mufuse inspect`)
```

`recordings/` is git-ignored, so the recordings never reach the public repo. The report lists
the headband name, firmware and software versions, but not its Bluetooth address.

Exit codes: `0` every check passed, `7` at least one check failed, `130` stopped with Ctrl+C.

## Rerunning part of it

```bash
uv run mufuse hardware-test --only power,interrupt
```

Check names: `find`, `firmware`, `streams`, `connect`, `contact`, `record`, `markers`, `power`,
`interrupt` (`markers` runs the recording step). Finding the headband always runs first.
`--quick` gives a shortened practice run (3 connections, 90-second recording); its report is
labelled as practice and doesn't count as the acceptance record.

## If something goes wrong

- **Step 1 finds nothing.** Check the headband is on and charged and the Muse app is closed.
  `uv run mufuse devices` runs the same scan.
- **Step 2 can't read the firmware.** Recordings still work without it. If step 3 then can't
  connect, the firmware query may have kept the Bluetooth link busy: rerun with
  `--only streams,connect,contact,record,power,interrupt`, record with
  `mufuse record --no-firmware`, and mention it in the PR.
- **Step 7 says the data never stopped.** The test waits up to 30 s after "Switch the headband
  OFF now" to see the data stop. Make sure the headband actually powers down.
- **The screen pauses during step 7.** Expected: a reconnect attempt can take up to 15 s while
  the headband is off. Directions still appear on time.

## Quick automatic checks (pytest)

```bash
uv run pytest -m hardware -s
```

Three fully automatic checks with no directions: the headband is discoverable, its firmware
version is readable, and every stream delivers ≥ 95% of nominal over 30 s. Useful after a
BrainFlow upgrade.
