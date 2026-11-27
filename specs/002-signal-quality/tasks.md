# Tasks: Signal Quality

**Input**: Design documents from `/specs/002-signal-quality/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: required. The constitution (VII) and `CLAUDE.md` make this project test-first: in every phase the test
tasks come first and must fail before the implementation tasks of that phase start.

**Organization**: one phase per user story of `spec.md`, in priority order. Each story can be shown working on the
simulator before the next one starts.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (a different file, and no dependency on an unfinished task)
- **[Story]**: the user story of `spec.md` the task belongs to (US1 to US5)
- **(you)**: a task only the user can do (it needs the headband or a browser). Claude never runs `--source athena`.
- A field written as `Entity.field` is defined in `data-model.md`; that file holds its allowed values and rules.
- "rules §N" means section N of `contracts/quality-rules.md`.

## Path Conventions

Single package: `src/mufuse/`, `tests/`, `scripts/` at the repository root (see `plan.md`, Project Structure).

---

## Phase 1: Setup

**Purpose**: the empty package and the shared test helpers.

- [X] T001 Create the package `src/mufuse/quality/__init__.py` (docstring only; the public names come in T039) and
  `tests/data/quality_reference/README.md`, which says that the files beside it are made by the simulator, hold no
  personal data, and are rewritten only by `scripts/make_quality_reference.py`
- [X] T002 Add shared helpers to `tests/conftest.py`: build EEG and MOTION `Chunk`s from arrays with timestamps;
  run a scripted `Wearer` through `Rehearsal` on `FakeClock` for N seconds and return the chunks as delivered

---

## Phase 2: Foundational (blocks every story)

**Purpose**: rules, answer types, the stretch cutter, and a simulator that can produce every fault and event
(FR-023). No signal judgement yet.

### Tests first

- [X] T003 [P] Tests in `tests/unit/test_quality_answer.py`: `Rules` is frozen and `RULES_VERSION == "1"`; the
  derived values `disturbances` (order), `clean(sensor)` and `reasons(sensor)`; the no-data answer; all as in
  `data-model.md`, "Derived values of an answer"
- [X] T004 [P] Tests in `tests/unit/test_quality_stretch.py` for rules §1, items 1 to 6: anchor; gap above 0.25 s;
  256 samples per stretch; samples left before a gap are not judged and one no-data answer covers the gap; when a
  stretch is judged (64 EEG samples past its end and motion up to its end, else the 1.0 s fallback, else at a gap
  or at finish); motion samples by timestamp; the same stretches for any way of splitting the input into chunks
  (seeded random sizes)
- [X] T005 [P] Tests in `tests/unit/test_simulated.py` (extend) for research R14: `Wearer.noisy`, `Wearer.flat`,
  `Wearer.railed` (from, to, channel) and `Wearer.turns` (from, to); a clench also shows on AF7 and AF8; a turn
  shows on the gyroscope; `grade_window` grades each fault as intended; a `Wearer` with the new fields empty gives
  the same samples as before for the same seed

### Implementation

- [X] T006 [P] `src/mufuse/quality/rules.py`: `RULES_VERSION`, the frozen dataclass `Rules` with every limit of
  `contracts/quality-rules.md`, and `RULES`. Field per `data-model.md`: `Rules.version`
- [X] T007 `src/mufuse/quality/answer.py`: the types `ContactState`, `Coverage`, `Blink`, `Span`, `QualityAnswer`
  with the derived values of T003. Fields per `data-model.md`: `ContactState.sensor`, `ContactState.state`,
  `ContactState.reason`, `ContactState.spread_uv`, `ContactState.mains_share`, `Coverage.level`, `Coverage.out`,
  `Blink.t`, `Blink.duration_s`, `Span.kind`, `Span.start`, `Span.end`, `QualityAnswer.start`,
  `QualityAnswer.end`, `QualityAnswer.rules`, `QualityAnswer.contact`, `QualityAnswer.coverage`,
  `QualityAnswer.eye`, `QualityAnswer.tension`, `QualityAnswer.tension_uv`, `QualityAnswer.movement`,
  `QualityAnswer.no_data`
- [X] T008 `src/mufuse/quality/stretch.py`: the cutter of rules §1 (it keeps samples, hands out stretches that are
  ready, and reports gaps). Fields per `data-model.md`: `Stretch.start`, `Stretch.end`
- [X] T009 `src/mufuse/acquisition/simulated.py`: the faults and events of T005. `tests/integration/test_rehearsal.py`
  and `tests/integration/test_sitting.py` stay green with no edit to `acceptance.py` or `signal_check.py`; if the H8
  rehearsal changes, correct the simulator's amplitude, never the check

**Checkpoint**: `uv run pytest -m "not hardware"` is green; nothing on screen has changed.

---

## Phase 3: User Story 1 - See which sensors can be trusted right now (Priority: P1) 🎯 MVP

**Goal**: a contact state with a reason for each sensor, once per stretch, and the coverage level, in the library
and in the live view (FR-001 to FR-006, FR-016, FR-018).

**Independent Test**: on the simulator, lift one sensor, then make one sensor noisy, then drop both ear sensors.
The view shows the right state and reason each time, and "reduced: forehead sensors good" in the last case.

### Tests first

- [X] T010 [P] [US1] Tests in `tests/unit/test_quality_contact.py` for rules §2: `settling`, `settling`, `good`;
  the count goes back to zero on a noisy stretch, a no-contact stretch and a gap; one reason for each fault (flat,
  railed, hum, floating, loud); "no contact" is told apart from "noisy" (FR-004); a loss shows within 2 s
  (FR-003); non-finite samples; the four coverage levels and the order of `out`; headband not worn (four sensors
  without contact)
- [X] T011 [P] [US1] Tests in `tests/unit/test_live_view.py` (extend): the sensor panel shows the engine's states;
  `waiting` before the first judged stretch; the Coverage line and every sensor text of `contracts/cli.md`,
  including "No sensor is touching skin. Is the headband on?"; nothing changes more often than once per stretch;
  only the three quality colours of `docs/BRAND.md` are used
- [X] T012 [P] [US1] Test in `tests/unit/test_quality_wording.py` (SC-009): render every text this story can show
  and check each against a list of words that describe a person's state; each later story adds its texts here
- [X] T013 [P] [US1] Test in `tests/integration/test_quality_cli.py`: `mufuse stream` on a scripted simulator
  source prints the Coverage line, and reads "reduced: forehead sensors good" when TP9 and TP10 are lifted

### Implementation

- [X] T014 [US1] `src/mufuse/quality/engine.py`: `QualityEngine(rules=RULES)` with `feed(chunks) -> Judged` and
  `finish() -> Judged` (`contracts/quality-interface.md`); contact per stretch through the unchanged
  `grade_window`, the hold counted in stretches, coverage. Until T026, `QualityAnswer.eye` and
  `QualityAnswer.tension` are `unavailable` and `QualityAnswer.movement` is `unknown` (never silent, FR-010)
- [X] T015 [US1] `src/mufuse/live_view.py`: `LiveStats` owns one `QualityEngine`; `contact()` reads the newest
  answer; the Coverage line under the sensor panel with the texts of `contracts/cli.md` (research R15)
- [X] T016 [US1] `src/mufuse/acquisition/contact.py`: remove `ContactTracker` and `HOLD_S`; `grade_window`,
  `mains_share`, `Reading`, `SensorView` and `tip` stay. Remove the tracker tests from `tests/unit/test_contact.py`
  (T010 covers the hold now)

**Checkpoint**: `uv run mufuse stream --source sim` shows contact and coverage from the engine. This is the MVP.

---

## Phase 4: User Story 2 - Blinks, jaw tension and head movement are marked (Priority: P2)

**Goal**: an eye mark and blink times, a tension level and mark, a movement mark, all from AF7, AF8 and the motion
sensors only (FR-006 to FR-010, FR-019).

**Independent Test**: on the simulator, 20 blinks, 20 jaw clenches and 20 head turns at known times. At least 18
of each are marked within 2 s, and quiet stretches stay unmarked.

### Tests first

- [X] T017 [P] [US2] Tests in `tests/unit/test_quality_motion.py` for rules §6: `unknown` under 26 samples; the
  gyroscope limit; the accelerometer limit on each axis; `still`; a sample at the stretch end belongs to the next
  stretch; a simulated turn is marked
- [X] T018 [P] [US2] Tests in `tests/unit/test_quality_tension.py` for rules §5: the level of a sine of known size
  inside the band equals its rms; hum at 50 and 60 Hz and the device lines do not raise the level; the smaller of
  two sensors; one sensor in use; `unavailable` with none; changing TP9 or TP10 changes nothing; a simulated
  clench is marked
- [X] T019 [P] [US2] Tests in `tests/unit/test_quality_blink.py` for rules §4: the filter state is carried, so the
  envelope is the same in one piece and in pieces; the limit from the 30 s before; both sensors must be above; the
  16-sample minimum; the eye mark window; `unavailable` in the first 5 stretches and with no forehead sensor in
  use; a run above 307 samples marks the stretch and is not a blink (eyes closed, slow drift); the 0.8 s rule;
  simulated blinks are found at their times
- [X] T020 [P] [US2] Tests in `tests/unit/test_quality_engine.py`: rules §3 (a forehead sensor in use), §7 (spans:
  marked stretches in a row are one span, a gap ends a span, long tension is one span) and §8 (clean; several
  reasons at once); no blink is reported from an `unavailable` stretch; the independent test above (20, 20, 20
  scripted events, at least 18 each)
- [X] T021 [P] [US2] Tests in `tests/unit/test_live_view.py` (extend) for the Signal line of `contracts/cli.md`
  (blink count, "blinks: not available", "muscle activity in the signal", "head movement", "movement: unknown"),
  and the same texts added to `tests/unit/test_quality_wording.py`

### Implementation

- [X] T022 [P] [US2] `src/mufuse/quality/motion.py`: rules §6
- [X] T023 [P] [US2] `src/mufuse/quality/tension.py`: rules §5
- [X] T024 [P] [US2] `src/mufuse/quality/blink.py`: rules §4; it produces `Blink.t` and `Blink.duration_s`
  (`data-model.md`)
- [X] T025 [US2] `src/mufuse/quality/answer.py`: build the spans of rules §7 from a row of answers (`Span.kind`,
  `Span.start`, `Span.end`, `data-model.md`)
- [X] T026 [US2] `src/mufuse/quality/engine.py`: feed the three detectors and fill `QualityAnswer.eye`,
  `QualityAnswer.tension`, `QualityAnswer.tension_uv` and `QualityAnswer.movement` (`data-model.md`); blinks go
  into `Judged.blinks`
- [X] T027 [US2] `src/mufuse/live_view.py`: the Signal line under the Coverage line

**Checkpoint**: the live view counts simulated blinks and names muscle activity and head movement.

---

## Phase 5: User Story 3 - Review the quality of a recorded session (Priority: P3)

**Goal**: `mufuse inspect` ends with a quality summary of any format-1 recording (FR-015, FR-017, FR-018).

**Independent Test**: record a simulated session with known faults at known times and ask for the summary. Every
share and count matches the script.

### Tests first

- [X] T028 [P] [US3] Tests in `tests/unit/test_quality_summary.py`: shares are taken over judged time; time without
  data is left out; a share with nothing to divide by is "not available", never 0; blinks per minute over the time
  the blink mark was available; the rules version is in the summary; the independent test above
- [X] T029 [P] [US3] Tests in `tests/integration/test_quality_cli.py` (extend): `mufuse inspect` prints the block
  "Signal quality (rules 1)" in the layout of `contracts/cli.md`; it works on a session that was not finalized and
  on one recorded before this feature; the recording's files are byte-identical afterwards; the exit codes of 001
  are unchanged; the summary texts are added to `tests/unit/test_quality_wording.py`
- [X] T030 [P] [US3] Test in `tests/integration/test_quality_speed.py` (SC-007): judging and summarizing a
  generated 60-minute session takes under 30 s

### Implementation

- [X] T031 [US3] `src/mufuse/quality/answer.py` and `src/mufuse/quality/engine.py`: the type `SessionQuality` and
  `judge(session, rules=RULES) -> SessionQuality`. Fields per `data-model.md`: `SessionQuality.rules`,
  `SessionQuality.answers`, `SessionQuality.blinks`, `SessionQuality.tension spans`,
  `SessionQuality.movement spans`
- [X] T032 [P] [US3] `src/mufuse/quality/summary.py`: `summarize(quality) -> QualitySummary`. Fields per
  `data-model.md`: `QualitySummary.rules`, `QualitySummary.judged_s`, `QualitySummary.no_data_s`, the per-sensor
  shares (good, settling, noisy, no contact, clean), the coverage shares, `QualitySummary.blinks`,
  `QualitySummary.blinks_per_min`, `QualitySummary.blink_available_s`, the tension share, the movement share,
  `QualitySummary.movement_unknown_s`
- [X] T033 [US3] `src/mufuse/cli.py`: `inspect` prints the summary after its present output

**Checkpoint**: `uv run mufuse inspect <session>` ends with "Signal quality (rules 1)".

---

## Phase 6: User Story 4 - One quality answer for every later feature (Priority: P4)

**Goal**: the guarantees of `contracts/quality-interface.md`: the same answer live and replayed, forehead only,
versioned, guarded by a stored reference (FR-011 to FR-015, FR-024, FR-025).

**Independent Test**: run a simulated session live and record it; replay the recording. The answers are identical
for every sensor and every stretch.

### Tests first

- [X] T034 [P] [US4] Test in `tests/integration/test_quality_replay.py` (SC-005): answers collected live while
  recording equal `judge()` on the recording, and equal the answers from `PlaybackSource` in seeded random chunk
  sizes; also with a dropout (a gap) and with a motion stream that stops
- [X] T035 [P] [US4] Test in `tests/integration/test_quality_ears.py` (SC-006): with TP9 and TP10 replaced by a
  no-contact signal, the AF7 and AF8 contact states, every mark, `tension_uv`, the blinks and the spans are
  identical; only the ear contact states and the coverage differ
- [X] T036 [P] [US4] Tests in `tests/unit/test_quality_engine.py` (extend): every answer names the rules version;
  an answer once returned never changes; no module in `src/mufuse/quality/` imports a clock, a network or a file
  module outside `labelled.py` and `public_set.py` (FR-024, read from the source with `ast`); `to_json` holds every
  field of the answer
- [X] T037 [P] [US4] Test in `tests/unit/test_quality_reference.py` (FR-025): `judge()` on the session in
  `tests/data/quality_reference/` reproduces `answers.json` within the tolerances of rules §9; the failure message
  names `RULES_VERSION` and `scripts/make_quality_reference.py`
- [X] T038 [P] [US4] Test in `tests/integration/test_quality_speed.py` (extend): judging costs under 5 ms per
  second of signal

### Implementation

- [X] T039 [US4] `src/mufuse/quality/answer.py`: `to_json(quality)`; `src/mufuse/quality/__init__.py`: the public
  names `QualityEngine`, `Judged`, `judge`, `summarize`, `to_json`, `RULES_VERSION`
- [X] T040 [US4] `scripts/make_quality_reference.py`: a simulated session of about 45 s with every fault and event
  (research R9); it writes the session and `answers.json`, and refuses when a measured value lies within 5% of its
  limit
- [X] T041 [US4] Run T040 and add its output in `tests/data/quality_reference/` (simulator data only)
- [X] T042 [US4] Correct in `src/mufuse/quality/engine.py` and `src/mufuse/quality/stretch.py` whatever T034 to
  T038 show; no rule is loosened to make a test pass

**Checkpoint**: features 003, 005 and 006 can import `mufuse.quality` and read answers without judging anything.

---

## Phase 7: User Story 5 - Prove the detectors on labelled data (Priority: P5)

**Goal**: a guided labelled session, a scorer, the rehearsed gate in CI, and the public set as a second score
(FR-020 to FR-024).

**Independent Test**: run the guided session on the simulator. The score report shows the number of cued events,
the number found, and pass or fail against 90%.

### Tests first: labelled session and scorer

- [X] T043 [P] [US5] Tests in `tests/unit/test_quality_labelled.py` for `contracts/labelled-session.md`: the
  schedule (times, counts, labels, `q:end` at 565 s); a cue becomes a marker label and back; each scoring rule
  (a blink counts for one cue only; a span that began before the cue's stretch does not count; quiet shares and
  "not scored" above 10% left out; false marks; the lift rule); a kind with no cues is "not scored"; the pass
  limits; the report layout of `contracts/cli.md`; the report holds no path and no device name
- [X] T044 [P] [US5] Test in `tests/integration/test_quality_gate.py`: the rehearsed labelled session on
  `FakeClock`: cues land in `markers.jsonl`, the score is 20 of 20 for each kind and 10 of 10 lifts, the replay is
  identical to live, the result is a pass; it runs in seconds
- [X] T045 [P] [US5] Tests in `tests/integration/test_quality_cli.py` (extend) for the exit codes of
  `contracts/cli.md`: `quality score PATH` 0, 1, 2, 6; `quality label` 0 whatever the score, 4, 5, and 130 with the
  recording finalized after Ctrl+C
- [X] T046 [P] [US5] Add the cue texts and the score report texts to `tests/unit/test_quality_wording.py`
- [X] T047 [P] [US5] Tests in `tests/unit/test_fetch_muse2_set.py`, with no network: `--from FILE` with a wrong
  checksum exits 1; a right one is unpacked into `--dest`; an archive entry that would leave the destination is
  refused; a refused download exits 1 and prints the browser steps of `quickstart.md`

### Implementation: labelled session and scorer

- [X] T048 [US5] `src/mufuse/quality/labelled.py`: the cue schedule, the `Guide` built from it (cues are written
  through the existing `Cue.marker` of `guide.py`), reading cues back from a session's markers, and the scripted
  `Wearer` of the rehearsal with a reaction time (research R14). Fields per `data-model.md`: `Cue.t`, `Cue.kind`,
  `Cue.sensor`
- [X] T049 [US5] `src/mufuse/quality/labelled.py`: the scorer and `ScoreReport`. Fields per `data-model.md`:
  `ScoreReport.rules`, `ScoreReport.allowed_s`, the per-kind found, total and pass, the quiet values, the lifts,
  `ScoreReport.replay_identical`, the overall pass
- [X] T050 [US5] `src/mufuse/cli.py`: the group `mufuse quality` with `label [--source] [--device] [--out]` and
  `score PATH`; `label` ends with the score report and the replay check
- [X] T051 [P] [US5] `scripts/fetch_muse2_set.py [--dest DIR] [--from FILE]`: download or take a file, check the
  MD5 of research R12, unpack outside the repo, print the folder. The package itself gets no network code

### Public set (second score, SC-003)

- [X] T052 [US5] Get the set with `uv run python scripts/fetch_muse2_set.py`. **(you, only if the download is
  refused)**: download `sourcedata.zip` in a browser and run `scripts/fetch_muse2_set.py --from <file>`. The set
  is untrusted data and never enters the repo
- [X] T053 [US5] Tests in `tests/unit/test_quality_public_set.py`, on a tiny folder the test builds in the layout
  found in T052: Muse 2 recordings and their cue times are read; a folder that is not the set gives exit code 2;
  cue times that cannot be read give "not scored" with the reason; head turns are not scored
- [X] T054 [US5] `src/mufuse/quality/public_set.py` and `mufuse quality score --public DIR` in `src/mufuse/cli.py`.
  If T052 could not be done, the result is "not scored" with the reason, never a pass

**Checkpoint**: `uv run mufuse quality label --source sim --out <dir>` records, scores and passes.

---

## Phase 8: Polish, freeze and the gate sitting

**Purpose**: fix the limits before they are scored, then prove them once on the headband.

- [ ] T055 Tune the limits marked *tuned* in `contracts/quality-rules.md` on the saved 001 sessions in
  `recordings/`, on the public set and on the simulator (research R13). Write the outcome as numbers only into
  `specs/002-signal-quality/research.md` (R13); no recording, path or device name goes into any committed file
- [ ] T056 Freeze rules v1 in one commit: `src/mufuse/quality/rules.py`, `contracts/quality-rules.md` (the word
  *tuned* removed), and `tests/data/quality_reference/` regenerated with `scripts/make_quality_reference.py`
- [X] T057 [P] Docs: `README.md` (quality block, `inspect` summary, `mufuse quality`), `docs/ROADMAP.md` (002
  status), `docs/KNOWN-ISSUES.md` (what 002 shows while the ear sensors are out), `CLAUDE.md` (architecture and
  commands)
- [X] T058 [P] `tests/hardware/README.md`: the 002 sitting (what to have ready, the command, what passes, what
  goes into the pull request and what never does)
- [X] T059 Full check: `uv run ruff format`, `uv run ruff check`, `uv run pyright`, `uv run pytest -m "not
  hardware"` in under 2 minutes with coverage at 80% or above (SC-010); fix what it shows in `src/mufuse/quality/`
- [X] T060 Run the simulator part of `specs/002-signal-quality/quickstart.md` from start to end and correct the
  file where a command or an expected result differs
- [ ] T061 **(you)** The gate sitting, after T056: headband on, phone Muse app closed,
  `uv run mufuse quality label --source athena` (guide: `tests/hardware/README.md`). It scores SC-001, SC-002,
  SC-004 and SC-005; `uv run mufuse inspect <session>` shows SC-008 (each stream at least 99.5% complete). A fail
  is reported as a fail; the 90% limit, P0 and H8 are not loosened
- [ ] T062 Tick the finished tasks in `specs/002-signal-quality/tasks.md`, then open the pull request to `main`
  with the score report's numbers (the report holds numbers only) and the public set's score or "not scored";
  merge only when CI is green on ubuntu and windows

---

## Dependencies & Execution Order

### Phases

- **Setup (1)** → **Foundational (2)** → the stories → **Polish (8)**.
- **US1 (3)** needs phase 2 only. It creates the engine.
- **US2 (4)** needs the engine of US1 (T014). Its three detectors (T022 to T024) need phase 2 only.
- **US3 (5)** needs US1. Its tension, movement and blink numbers need US2.
- **US4 (6)** needs `judge()` of US3 (T031) and the detectors of US2.
- **US5 (7)** needs US2 (marks to score) and `judge()` (T031). The replay check uses what US4 proves.
- **T055 and T056** need every story. **T061** needs T056: limits are frozen before they are scored.

### Inside a phase

- Tests first, and they fail first.
- Phase 2: T006 → T007 → T008; T009 stands alone.
- US1: T014 → T015 → T016 (the tracker goes only when the live view no longer reads it).
- US2: T022, T023, T024 in parallel → T025 → T026 → T027.
- US3: T031 → T032, T033.
- US4: T039 → T040 → T041 → T037 can pass; T042 last.
- US5: T048 → T049 → T050; T051 → T052 → T053 → T054.

### Parallel Opportunities

- Phase 2: T003, T004, T005 together; T006 beside T009.
- US1: T010 to T013 together.
- US2: T017 to T021 together; then T022, T023, T024 together.
- US3: T028, T029, T030 together; T032 beside T033.
- US4: T034 to T038 together.
- US5: T043 to T047 together; T051 beside T048 to T050.
- Polish: T057 beside T058.

## Parallel Example: User Story 2

```text
Tests first, all at once:
  T017 tests/unit/test_quality_motion.py
  T018 tests/unit/test_quality_tension.py
  T019 tests/unit/test_quality_blink.py
  T020 tests/unit/test_quality_engine.py
  T021 tests/unit/test_live_view.py

Then the three detectors, all at once:
  T022 src/mufuse/quality/motion.py
  T023 src/mufuse/quality/tension.py
  T024 src/mufuse/quality/blink.py
```

## Implementation Strategy

### MVP first (US1 only)

1. Phase 1 and phase 2.
2. Phase 3 (US1).
3. Stop and check: `uv run mufuse stream --source sim` shows contact and coverage from the engine.

### Then one story at a time

US2 (marks) → US3 (summary) → US4 (guarantees and the reference) → US5 (the gate on the simulator). After each
story the suite is green and the story's independent test passes on the simulator.

### Last

Tune (T055), freeze (T056), then the one headband sitting (T061). The order matters: a detector scored on the
recording it was tuned on proves nothing.

## Notes

- One branch (`002-signal-quality`), one pull request. Commit after each task or small group of tasks.
- `signal_check.py` and `acceptance.py` are not edited; P0 and H8 stay as they are.
- Nothing for AF7, AF8 or any mark reads TP9 or TP10 (FR-006, issue #12).
- Texts name a sensor or a signal, never a state of the person; tension is "muscle activity in the signal".
- Recordings, logs and the public set never enter the repo. The reference in `tests/data/quality_reference/` is
  made by the simulator.
