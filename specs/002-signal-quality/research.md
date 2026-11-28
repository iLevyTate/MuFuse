# Research: Signal Quality

Sources: the code of feature 001; `docs/research/2026-11-26-prior-art-and-datasets-survey.md`, section 3.2;
`docs/KNOWN-ISSUES.md`. Every number called a limit below is an initial value. Limits are tuned in build step 9 and
then frozen as rules v1 (see R13). The exact v1 definitions are in `contracts/quality-rules.md`.

## R1 Stretch
- **Decision**: a stretch is 256 consecutive EEG samples (1.0 s), not overlapping. The first stretch starts at the
  first EEG sample. A step of more than 0.25 s between two EEG timestamps is a gap: the unfinished stretch before it
  is dropped and a new one starts at the first sample after it. Time not covered by a stretch is "no data".
- **Rationale**: one second is the window the contact grade of 001 already uses, it gives 1 Hz resolution for the hum
  and tension spectra, and it meets "at least once a second" (FR-001). Counting samples, not seconds, makes the cut
  independent of how the samples arrived. 0.25 s is the gap limit `Retimer` already uses, so both agree on what a
  gap is.
- **Alternatives**: 0.5 s stretches (2 Hz bins, too coarse to leave out single lines); 1 s windows every 0.25 s
  (four times the work and four answers that mostly repeat each other); stretches on the wall clock (not
  reproducible in replay).

## R2 Same answer live and in replay
- **Decision**: the engine depends on sample values and sample timestamps only. It keeps the samples of each stream
  until a stretch can be judged. A stretch `[a, a + 1 s)` is judged when 64 EEG samples (0.25 s) past its end
  have arrived and the newest motion timestamp is at or past `a + 1 s`. If motion stays behind, it is judged once
  the newest EEG timestamp is at or past `a + 2 s`. Motion samples belong to a stretch by timestamp. All chunks of
  one `feed()` call are stored before any stretch is judged. No rule reads a clock.
- **Rationale**: a recording holds exactly the samples and timestamps the live run saw (retiming happens in the
  source, before the writer), but in other chunk sizes: `PlaybackSource` can hand over a whole stream at once.
  Closing on timestamps makes chunk size and stream order irrelevant. The second condition lets the answer continue
  when the motion stream stops; such a stretch has no motion samples in it either way, live or replayed.
- **Limit of the argument**: it assumes a motion sample stamped `t` never arrives later than an EEG sample stamped
  `t + 1 s`. BrainFlow stamps on arrival, so this holds by construction. `test_quality_replay.py` checks it on the
  simulator with random chunk sizes, and the labelled session checks it on the headband (R11).
- **Alternatives**: store the live answers in a new file and read them back (forbidden by the spec's storage
  assumption, and it would hide a difference instead of preventing it).

## R3 Contact per stretch
- **Decision**: each sensor's 256 samples go through the existing `grade_window()` unchanged (grades none, noisy,
  good; reasons flat, railed, hum, floating, loud; limits 1 µV, 75 µV, 98% of ±725 µV, 60% mains share at 50 and
  60 Hz). The hold becomes a count: a sensor is `good` from its third good stretch in a row, and `settling` before
  that. Any other grade is reported at once and resets the count. `ContactTracker`, which held on the wall clock, is
  removed; the live view reads the engine.
- **Rationale**: the grade is already measured against the real device and tested. Only its clock stood in the way
  of FR-012. A loss shows after at most one full stretch, inside the 2 s of FR-003; the state can change only once
  a second, which is also the flicker rule of the spec.
- **Alternatives**: keep `ContactTracker` for the screen and add a second tracker for the answers (two truths on
  one screen); looser limits from muse.js (150 µV) or Grosselin 2019 (300 µV): rejected, 75 µV is stricter than
  both and is what P0 uses.

## R4 Coverage
- **Decision**: from the four contact states of a stretch: `full` (four good), `reduced` (AF7 and AF8 good),
  `one_forehead` (exactly one of them good), `none`. `settling` counts as not good. Every level below full lists
  the sensors that are out.
- **Rationale**: FR-005, word for word. Only AF7 and AF8 decide whether a session is usable (FR-006, issue #12).

## R5 Blinks
- **Decision**: per forehead sensor: causal Butterworth band-pass 1-10 Hz (order 2, second-order sections, state
  carried from stretch to stretch), absolute value, moving mean over 32 samples. Limit per stretch: median plus 4
  scaled MADs of that envelope over the previous 30 s (taken at every 8th sample), and at least 15 µV. A blink is a
  run above the limit that lasts 0.06 to 1.2 s and shows on every forehead sensor that is touching skin; two onsets
  less than 0.8 s apart are one blink. Its time is the onset. A stretch gets the eye mark when a run of 0.06 s or
  longer, with no upper limit, comes within 0.125 s of it; the envelope lags the eye by about that much, and this is
  why a stretch is judged 0.25 s after its end (R2). After a start or a gap the detector needs 5 s; until then, and
  when no forehead sensor is touching, blinks are "not available".
- **Rationale**: this is the survey's recipe (band 1-10 Hz, envelope, robust z above 4, 0.8 s refractory, width
  under 1.2 s) with its two non-causal parts replaced: the Hilbert envelope by rectify-and-smooth, the whole-file
  statistics by the preceding 30 s. A run longer than 1.2 s is slow eye movement or drift: it marks the stretch but
  is not counted as a blink, which covers the eyes-closed case of the spec. Asking for both sensors removes single
  electrode pops.
- **Alternatives**: a fixed amplitude limit (fails across people and fits); template matching (needs a template
  per person); the Muse's own blink flags (not in BrainFlow, and not ground truth).
- **Seen while building (2026-11-27, simulator)**: the 1 Hz high-pass of the band makes the envelope swing back
  after a large blink (150 µV, 0.3 s): runs of 16-21 samples above the 15 µV floor about 0.67-0.77 s after the
  onset. They are eye events, so they also mark the next stretch, and only the 0.8 s rule keeps them from counting
  as blinks. Two blinks 0.45-0.8 s apart therefore count as two, the second being the first one's swing-back.
  To check when the limits are tuned (T055): the swing-back on real blinks, and whether the floor or the 0.8 s
  rule needs to move.

## R6 Muscle tension
- **Decision**: per forehead sensor and stretch: mean removed, Hann window, power spectrum; the level is the root
  of the summed power in 30-48 Hz and 66-98 Hz, without the bins within 1.5 Hz of 42.67 Hz and 85.33 Hz. The level
  of the stretch is the smaller of the two sensors' levels when both are touching skin, else that of the one that
  is. The stretch is marked when the level is above 10 µV. Neighbouring marked stretches form one span with a start
  and an end.
- **Rationale**: muscle signal is broadband from about 20 Hz upward. The band must stay under the 128 Hz Nyquist
  limit and clear of mains (50, 60, 100, 120 Hz) and of the Athena's own lines (multiples of 21.33 Hz); MNE's
  default of 110-140 Hz does not fit. A spectrum per stretch leaves single lines out by bin and needs no filter
  state, so it cannot differ between live and replay. Taking the smaller level stops one badly seated sensor from
  reading as tension. A fixed limit keeps the rule simple; a personal baseline belongs to feature 003.
- **Known weakness**: a sensor that touches but is loud across the band reads as tension when it is the only one
  touching. The stretch is "not clean" in both cases, with both reasons listed.
- **Alternatives**: a band-pass filter with notches (five filters and their states for the same number); the ear
  sensors, where the jaw signal is stronger (forbidden by FR-006).

## R7 Movement
- **Decision**: per stretch, from its motion samples (52 expected): `moving` when the root mean square of the
  gyroscope magnitude is above 20 deg/s or the standard deviation of any accelerometer axis is above 0.05 g, else
  `still`. Fewer than 26 samples give `unknown`. Neighbouring `moving` stretches form one span.
- **Rationale**: a head turn is a rotation, so the gyroscope carries it; the accelerometer adds bumps and nods.
  Both units are physical (deg/s, g), so one limit holds for every session. "Unknown" is its own value because a
  silent motion stream must never read as a still head (FR-010).
- **Alternatives**: a movement mark from the EEG itself (cannot tell movement from poor contact); OpenNeuro
  ds009136 for tuning (has no AF7/AF8 and is not needed for two limits).

## R8 One answer
- **Decision**: a stretch-level set of disturbances (`eye`, `tension`, `movement`, `movement_unknown`,
  `eye_unavailable`, `tension_unavailable`) plus one contact state per sensor. A sensor is clean in a stretch when
  its contact is `good` and the set is empty. The reasons of a sensor are its own contact reason, if any, followed
  by the stretch's disturbances. Optics consumers read the movement value of the same answer (FR-009).
- **Rationale**: the Muse references every sensor to the forehead, so a blink or a clench disturbs all four
  channels; one set per stretch is honest and simple. Reasons stay separate values, so a later feature can accept,
  say, eye marks but not movement without judging anything itself (FR-014).
- **Alternatives**: a numeric quality score per sensor (hides the reason and invites thresholds elsewhere).

## R9 Rules version and reference recording
- **Decision**: `RULES_VERSION = "1"` in `quality/rules.py`, beside every limit in one frozen dataclass. It is part
  of every answer, summary and score report. A simulator-made session of about 45 s with every fault and event sits
  in `tests/data/quality_reference/` with `answers.json`. The test demands equal states, marks and times, and
  levels within 1e-6 relative. The reference is built so that no level lies within 5% of a limit. A change that
  alters any answer must raise the version and regenerate `answers.json` in the same commit
  (`scripts/make_quality_reference.py`).
- **Rationale**: constitution IV and FR-025. A stored file, not a session generated at test time, because sine and
  random-number details may differ between platforms and library versions; the stored samples cannot. The 5%
  margin keeps the last bits of an FFT from flipping a state between ubuntu and windows.
- **Alternatives**: a real recording as reference (personal data, never committed); a checksum of the answers
  (says that something changed, not what).

## R10 Where cue times live
- **Decision**: cues are system markers in the existing `markers.jsonl`, written by the mechanism `guide.py`
  already has (`Cue.marker`), with labels `q:blink`, `q:clench`, `q:turn`, `q:lift:AF7`, `q:down:AF7`,
  `q:quiet_open`, `q:quiet_closed`, `q:end`. The recording format stays at version 1.
- **Rationale**: the spec allows one new stored thing, the cue times, and asks that they are deleted with their
  recording. Markers already are. No new file, no new reader.

## R11 Labelled session and scoring
- **Decision**: `mufuse quality label` records about 9.5 minutes with on-screen cues: 20 s to settle; 60 s quiet,
  eyes open; 60 s quiet, eyes closed (the terminal bell ends it); 20 blinks, one every 4 s; 20 jaw clenches of 1 s,
  one every 5 s; 20 head turns, one every 5 s; 10 lifts of a forehead sensor for 5 s, one every 10 s, AF7 and AF8
  in turn. `mufuse quality score PATH` judges the recording and reports per kind: found, total, false marks, pass
  or fail, with the rules version.
  - Blink: found when a blink's onset lies in the 2 s after its cue.
  - Clench and turn: found when a tension or movement span starts in the stretch that contains the cue or in the
    2 s after the cue. A span that was already running before that stretch does not count.
  - Quiet: share of quiet stretches marked for tension and for movement (limit 5% each); blinks per minute with
    eyes closed (limit 2).
  - Lift: from the first stretch after the cue in which the sensor is no longer good, "no contact" must follow
    within 2 s, and "noisy" may not last longer than 2 s before the sensor is put back (9 of 10).
  - At its end the command replays the session it just recorded and compares the answers with the live ones
    (SC-005 on the headband).
- **Rationale**: the cue is the label (spec). Tension and movement are judged per stretch, so their spans start on
  a stretch boundary, up to 1 s before the muscle or the head moved; "the stretch that contains the cue" is the
  honest reading of "within 2 seconds after its cue" at that resolution, and the report says so. The lift rule
  measures the detector, not the person's reaction time to the cue.
- **Spec touch**: the Labels assumption in `spec.md` gains one sentence stating the stretch rule above.
- **Alternatives**: marks with sample-exact starts for tension and movement (a second, filter-based detector for
  each, only to serve the scorer); labels typed by hand afterwards (slow, and subjective).

## R12 Public set
- **Decision**: Lee and Ahn, "EEG dataset of consumer- and research-grade systems", figshare
  `10.6084/m9.figshare.30162868.v1`, CC BY 4.0. Only `sourcedata.zip` is needed (400 MB, MD5
  `cdc629a35f58b1faf7a9981a86783786`). `scripts/fetch_muse2_set.py` downloads it to the user's cache folder
  (`platformdirs`, outside the repo), checks the MD5 and unpacks it; `--from FILE` verifies and unpacks a copy the
  user downloaded in the browser. `mufuse quality score --public DIR` scores cued blinks and clenches of the Muse 2
  recordings. Head movements are not scored on it.
- **Rationale**: it is the only open set with cued blinks and clenches on the same four sensor sites. It is a
  second score (SC-003), not the gate. The network code stays in a script, so the installed package cannot reach
  the network at all (FR-024).
- **Open at planning time**: figshare answered a plain scripted request with HTTP 403 on 2026-11-26, and the
  set's README could not be read that way. The reader (`public_set.py`) is therefore written against the unpacked
  files in build step 8. If the cue times cannot be recovered from the files, SC-003 is reported as "not scored"
  with the reason. It is never reported as passed without a score.
- **Alternatives**: vendoring a sample (forbidden: third-party data stays out of the repo); Zenodo 8429740 (its
  labels are the Muse's own flags); the Kaggle facial-movement set (no licence).
- **Found when the set was fetched (2026-11-27)**: the scripted download now works (figshare redirects to its
  storage; the checksum matched). `sourcedata/sub-XX/` holds one EDF+ file per task and device; the Muse 2 files
  (`…_acq-Muse2_eeg.edf`, 26 subjects for each task used here) carry TP9, AF7, AF8, TP10 at 256 Hz and the cues as
  annotations on the file's own clock: `…Number_01` task start, twenty `…Number_02` "task performing" beeps 3 s
  apart, `…Number_03` task end. The README names four tasks, EB, BT, MVO and MVC, without saying which movement
  each is; the derivatives hold the same events, timed on another device. EB is the eye-blink task. The clench
  task is inferred from the data: in the second after each beep (subjects 1-7, median) the louder of the ear
  sensors reads 12.2 µV of tension-band level for BT, 12.1 for MVO, 7.9 for MVC and 6.5 for EB, so BT (or MVO) is
  jaw muscle work; BT is used. On the forehead alone the same clench reads only 4.4 µV (rest 2.3), against the
  10 µV tension limit.
- **First score of rules v1 as drafted (untuned)**: blinks 367 of 520 (70.6%), jaw clenches 118 of 520 (22.7%);
  SC-003 not met. Both are inputs to the tuning of R13, not a verdict on the gate, which is the Athena session.

## R13 Where the limits come from
- **Decision**: the initial limits come from the survey and from the simulator's known amplitudes. In build step 9
  they are tuned on three sources that exist without a new sitting: the user's saved 001 acceptance sessions (H8
  holds cued blinks and clenches, H4 a long quiet stretch), the public set, and the simulator. Then they are frozen
  as rules v1 and the reference answers are regenerated. Only after that is the gate sitting recorded.
- **Rationale**: scoring a detector on the recording it was tuned on proves nothing. Freezing first costs no extra
  sitting, because tuning material is already on disk. The saved sessions never leave the machine and are never
  committed.

## R14 Simulator
- **Decision**: `Wearer` gains `noisy`, `flat` and `railed` (from, to, channel) and `turns` (from, to); a clench
  also adds broadband signal on AF7 and AF8 (30 µV, a guess, below the 80 µV at the ears); a turn adds a gyroscope
  swing of about 100 deg/s and a small accelerometer change. `labelled.py` builds the wearer for the labelled
  session from its cue list, as `wearer_for()` does for the 001 checks, with a reaction time.
- **Rationale**: FR-023. One cue list drives both the screen and the rehearsed wearer, so the whole gate (label,
  score, pass) runs in CI. As `simulated.py` already says: a green rehearsal proves the pipeline, not the
  physiology.

## R15 Live view and inspect
- **Decision**: `LiveStats` owns one `QualityEngine`. The sensor panel keeps its layout and reads the engine's
  contact states; a line under it shows coverage with the sensors that are out, the blink count, and "muscle
  activity in the signal" or "head movement" when the newest stretch is marked. `mufuse inspect` prints the summary
  of FR-017 after its present output. Colours stay the three quality tokens of `docs/BRAND.md`.
- **Rationale**: one source for the screen and for the answers. No new screen, no horseshoe.

## R16 Looked at and not used
- BrainFlow `DataFilter.get_signal_quality`: checks non-finite, clipped and flat samples, which `grade_window`
  already covers, and has no hum check. Not used.
- Stream 0x53 (worn / not worn): BrainFlow skips the tag; needs driver work and a hardware check. Deferred.
- Ravi Athena set (Zenodo 23744414): a possible later check of the contact grade; needs an importer. Not in this
  feature.
- ASR (asrpy, meegkit), autoreject, pyprep, pyRiemann Potato: repair or batch tools with heavy or blocked
  dependencies on Python 3.15. Rejected in the survey.

## R17 First labelled sitting on the Athena (2026-11-27, tuning data)
- **What it is**: the first of the two sittings in `quickstart.md`, scored on rules v1 as drafted (untuned). It is
  tuning data for R13, not the gate. Numbers only; the recordings stay on the machine.
- **Full session**: blinks 19 of 20, jaw clenches 20 of 20, head turns 18 of 20, sensor lifts 9 of 10: each
  passes. Quiet fails: muscle activity 0.0%, head movement 0.9%, 5.5 blinks per minute with eyes closed (limit 2),
  6 false marks (five blinks in the eyes-closed minute, one movement mark in the eyes-open minute).
- **Why quiet failed**: the terminal bell that ends the eyes-closed minute made no sound in Windows Terminal, and
  the eyes were opened during that minute to check the screen. The five blinks are real eye openings, so the fail
  is kept as recorded and is not a fault of the blink rule. The bell cue now also plays a tone on the sound card
  (`src/mufuse/sound.py`); it was heard in the repeat.
- **Eyes-closed minute repeated alone** (80 s, same cue label, with the tone): 55 stretches judged, 0 blinks, muscle
  activity 0.0%, head movement 0.0%, 0 false marks: quiet passes. AF7 and AF8 had good contact in all 55.
- **Where the misses fall**: every miss is at the start of its block (the first blink cue, the first two turn
  cues, the first AF7 lift). That points at the wearer finding the movement, not at a limit.
- **Not settled**: no blink was marked in the eyes-open minute, and it is not known whether one was made. The ear
  sensors came and went (issue #12); no conclusion is drawn from them.
- **Standing**: each kind has passed once on the drafted limits, across two recordings. The gate is still one
  full session recorded after the limits are frozen (T056, then T061).
