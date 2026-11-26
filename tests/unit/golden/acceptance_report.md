# MuFuse hardware acceptance, run 20261126-100000

One sitting with the Muse S Athena headband. This report is built from the numbers the checks saved: it holds no paths, names, addresses or samples.

| Run | 20261126-100000 |
| --- | --- |
| Date | 2026-11-26, 10:00 to 10:26 |
| Source | Muse S Athena headband over BrainFlow |
| Headband | MuseS-****, preset p1041, firmware 3.1.19 |
| Battery | 82% at the start (P0), 77% at the end (H4) |
| MuFuse | 0.1.0 at commit abc1234 |
| BrainFlow | 5.24.0 |
| OS | Windows 11 |
| Result | 7 of 9 requested checks passed: 1 FAIL, 1 SKIPPED |

## Checks

| Check | Success criterion | Outcome | Attempts | Key numbers |
| --- | --- | --- | --- | --- |
| P0 · Preflight: fit, battery and streams | - | PASS | 1 | battery 82% (need ≥ 20%) · EEG 99.90%, motion 99.90%, optics 99.90% of the nominal rate (need ≥ 95%) · still windows the channel check called ok: TP9 100%, AF7 100%, AF8 100%, TP10 100% (need ≥ 80%) |
| H8 · Channel check reacts to contact, jaw and blinks | - | PASS | 2 | lifting the left ear sensor changed TP9 in 100% of windows (need ≥ 50%), against 0% at rest (need < 50%) · jaw clench raised the std to 5.0 times rest on TP9 and 5.1 times on TP10 (need ≥ 3 times on either) · blink-like deflections: AF7 9, AF8 8 (not judged) |
| H6 · Keyboard markers | SC-004: Markers on reload sit within ±1 sample (±4 ms for EEG) of their capture time. | SKIPPED | 0 | - |
| H7 · Ctrl+C mid-recording leaves a readable session | SC-005: 100% of sessions interrupted by Ctrl+C or device loss reload without error. | PASS | 1 | 3969 EEG samples saved · recording stopped +1.1 s from the Ctrl+C cue (need within 10 s) |
| H5 · Power-cycle recovery | SC-003: After a 10-second headband power cycle, streaming resumes automatically within 20 seconds and the gap is recorded with duration accurate to ±0.5 s. | FAIL | 1 | gaps recorded: 1 · signal away for 24.7 s (need ≥ 8 s) · streaming back +25.3 s from the power-on cue (need ≤ 20 s after it, +3 s tolerance) · recorded gap 24.66 s against a hole of 24.70 s in the EEG data (need within ±0.5 s) |
| F1 · fNIRS optics: which channels are ambient light | - | PASS | 1 | rows that behaved as ambient light: OPT5, OPT6, OPT7, OPT8 (expected OPT5 to OPT8, BrainFlow wire order) · room light added 3000 to 3000 counts over covered on those four rows (need ≥ 1000) |
| H4 · 10-minute recording completeness | SC-002: A 10-minute recording has < 0.5% missing samples on every stream when the headband is within 2 m. | PASS | 1 | EEG 99.72%, motion 99.72%, optics 99.72% complete (need ≥ 99.50%) · samples missing: EEG 430 (400 lost on the headset link), motion 430 (400 lost on the headset link), optics 430 (400 lost on the headset link) |
| H3 · Time to first signal, 10 connects in a row | SC-001: From headband power-on to live signal on screen in ≤ 15 seconds in ≥ 9 of 10 attempts. | PASS | 1 | 9 of 10 connects reached EEG within 15 s (need ≥ 9 of 10) · slowest 16.2 s |
| H1/H2 · Discovery and 30 s of every stream | - | PASS | 1 | the hardware tests' own verdict (`pytest -m hardware`) |

A failed check keeps its session on disk. This prints every rule with its numbers from the saved sessions, without the headband: `uv run python scripts/hw_acceptance.py --rejudge 20261126-100000`

A check with no success criterion guards or informs the others: P0 is the preflight, H8 feeds the channel check of feature 002, F1 the optics of feature 004, and H1/H2 are the hardware tests. Attempts counts the recordings that were judged.

## Skipped and not run

- H6: SKIPPED. Reason: skipped at the keyboard.

## Calibration

Numbers this run saved for tuning the live channel check (feature 002) and for the optics (feature 004). Suggestions only: nothing here changes `signal_check.py`. A change to it goes into a reviewed commit that cites this run and is checked with `--rejudge`.

The robust spread is what the live channel check measures in each 2 s window: 1.4826 times the median distance from the median, which a short blink does not move. The plain std is the usual standard deviation of the same window.

**EEG robust spread per 2 s window, µV: 5th percentile / median / 95th percentile**

| Phase | TP9 | AF7 | AF8 | TP10 |
| --- | --- | --- | --- | --- |
| P0 sitting still | 9 / 14 / 19 | 9 / 14 / 19 | 9 / 14 / 19 | 9 / 14 / 19 |
| H8 at rest | 10 / 15 / 20 | 10 / 15 / 20 | 10 / 15 / 20 | 10 / 15 / 20 |
| H8 left ear sensor lifted | 30 / 39 / 50 | 30 / 39 / 50 | 30 / 39 / 50 | 30 / 39 / 50 |
| H8 jaw clenched | 80 / 90 / 120 | 80 / 90 / 120 | 80 / 90 / 120 | 80 / 90 / 120 |
| H8 blinking | 15 / 25 / 35 | 15 / 25 / 35 | 15 / 25 / 35 | 15 / 25 / 35 |
| H4 whole recording (worn or on the desk) | 8 / 13 / 30 | 8 / 13 / 30 | 8 / 13 / 30 | 8 / 13 / 30 |

**What the live channel check called those windows, % of windows: ok / noisy / flat / railed**

| Phase | TP9 | AF7 | AF8 | TP10 |
| --- | --- | --- | --- | --- |
| P0 sitting still | 100 / 0 / 0 / 0 | 100 / 0 / 0 / 0 | 100 / 0 / 0 / 0 | 100 / 0 / 0 / 0 |
| H8 at rest | 100 / 0 / 0 / 0 | 100 / 0 / 0 / 0 | 100 / 0 / 0 / 0 | 100 / 0 / 0 / 0 |
| H8 left ear sensor lifted | 100 / 0 / 0 / 0 | 100 / 0 / 0 / 0 | 100 / 0 / 0 / 0 | 100 / 0 / 0 / 0 |
| H8 jaw clenched | 0 / 100 / 0 / 0 | 0 / 100 / 0 / 0 | 0 / 100 / 0 / 0 | 0 / 100 / 0 / 0 |
| H8 blinking | 100 / 0 / 0 / 0 | 100 / 0 / 0 / 0 | 100 / 0 / 0 / 0 | 100 / 0 / 0 / 0 |
| H4 whole recording (worn or on the desk) | 100 / 0 / 0 / 0 | 100 / 0 / 0 / 0 | 100 / 0 / 0 / 0 | 100 / 0 / 0 / 0 |

**Plain numbers: median std µV / median peak-to-peak µV / % of samples within 5% of full scale**

| Phase | TP9 | AF7 | AF8 | TP10 |
| --- | --- | --- | --- | --- |
| P0 sitting still | 14 / 56 / 0 | 14 / 56 / 0 | 14 / 56 / 0 | 14 / 56 / 0 |
| H8 at rest | 15 / 60 / 0 | 15 / 60 / 0 | 15 / 60 / 0 | 15 / 60 / 0 |
| H8 left ear sensor lifted | 215 / 156 / 30 | 215 / 156 / 30 | 215 / 156 / 30 | 215 / 156 / 30 |
| H8 jaw clenched | 90 / 360 / 0 | 90 / 360 / 0 | 90 / 360 / 0 | 90 / 360 / 0 |
| H8 blinking | 25 / 100 / 0 | 25 / 100 / 0 | 25 / 100 / 0 | 25 / 100 / 0 |
| H4 whole recording (worn or on the desk) | 13 / 52 / 0 | 13 / 52 / 0 | 13 / 52 / 0 | 13 / 52 / 0 |

**Mains hum, % of the EEG power above 1 Hz: 50 Hz / 60 Hz**

| Phase | TP9 | AF7 | AF8 | TP10 |
| --- | --- | --- | --- | --- |
| P0 sitting still | 2 / 0 | 2 / 0 | 2 / 0 | 2 / 0 |
| H8 at rest | 2 / 0 | 2 / 0 | 2 / 0 | 2 / 0 |
| H8 left ear sensor lifted | 2 / 0 | 2 / 0 | 2 / 0 | 2 / 0 |
| H8 jaw clenched | 2 / 0 | 2 / 0 | 2 / 0 | 2 / 0 |
| H8 blinking | 2 / 0 | 2 / 0 | 2 / 0 | 2 / 0 |
| H4 whole recording (worn or on the desk) | 2 / 0 | 2 / 0 | 2 / 0 | 2 / 0 |

**F1 optics, median counts per phase**

| Row | Wire role | On head | Room light | Covered | Light again | Room light over covered | Pulse share on head |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OPT1 | red | 100001 | 300 | 60000 | 310 | -59700 | 40% |
| OPT2 | red | 100002 | 300 | 60000 | 310 | -59700 | 40% |
| OPT3 | red | 100003 | 300 | 60000 | 310 | -59700 | 40% |
| OPT4 | red | 100004 | 300 | 60000 | 310 | -59700 | 40% |
| OPT5 | ambient | 338005 | 341200 | 338000 | 341000 | +3000 | 1% |
| OPT6 | ambient | 338006 | 341200 | 338000 | 341000 | +3000 | 1% |
| OPT7 | ambient | 338007 | 341200 | 338000 | 341000 | +3000 | 1% |
| OPT8 | ambient | 338008 | 341200 | 338000 | 341000 | +3000 | 1% |
| OPT9 | 730 nm | 100009 | 300 | 60000 | 310 | -59700 | 40% |
| OPT10 | 730 nm | 100010 | 300 | 60000 | 310 | -59700 | 40% |
| OPT11 | 730 nm | 100011 | 300 | 60000 | 310 | -59700 | 40% |
| OPT12 | 730 nm | 100012 | 300 | 60000 | 310 | -59700 | 40% |
| OPT13 | 850 nm | 100013 | 300 | 60000 | 310 | -59700 | 40% |
| OPT14 | 850 nm | 100014 | 300 | 60000 | 310 | -59700 | 40% |
| OPT15 | 850 nm | 100015 | 300 | 60000 | 310 | -59700 | 40% |
| OPT16 | 850 nm | 100016 | 300 | 60000 | 310 | -59700 | 40% |

BrainFlow raw counts, rows in wire order. OpenMuse and Mind Monitor show counts ÷ 32768: the covered level of OPT5 to OPT8, about 338000 counts here, reads about 10.3 there. The role is the one expected for wire order; F1's outcome says whether this headband agrees. Pulse share: the part of a row's 0.1 to 10 Hz power between 0.7 and 3 Hz, where a heartbeat shows.

### Suggestions

- Noisy threshold (NOISY_UV, now 75 µV): at rest the spread stayed under 20 µV (TP9) in 95% of windows; with the jaw clenched it stayed above 80 µV (TP9) in 95% of windows. A threshold of about 40 µV, the geometric midpoint, would separate the two. The threshold in force lies inside that gap, 55 µV above rest and 5 µV under the clench. Blinks stayed under it: 35 µV at most (AF7).
- Rail threshold (RAIL_UV, now 1000 µV): cannot be reached. The amplifier ends at about ±725 µV (BrainFlow 5.23 and later) and each window is centred before it is checked, so a channel stuck at the rail reads flat, never railed. Counting the samples within 5% of full scale (beyond about 690 µV) before centring would see it: 30% of the lifted TP9 samples were there, 0% at rest.
- Flat threshold (FLAT_UV, now 1 µV): the lowest spread at rest was 10 µV (TP9), clear of it. No change suggested.
- Lifted sensor: with the left ear sensor off the skin the channel check still called TP9 ok in 100% of windows (noisy 0%, flat 0%, railed 0%); the robust spread was 39 µV against 15 µV at rest, the plain std 215 µV against 15 µV. Telling a lifted sensor needs a measure other than the robust spread.

## Reproduce

- The same checks in a new sitting: `uv run python scripts/hw_acceptance.py`
- Only what this run has not passed: `uv run python scripts/hw_acceptance.py --resume 20261126-100000`
- Judge this run's saved sessions again, without the headband: `uv run python scripts/hw_acceptance.py --rejudge 20261126-100000`
- Rehearse the sitting on the simulator: `uv run python scripts/hw_acceptance.py --rehearse`
