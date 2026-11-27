# Implementation Plan: Signal Quality

**Branch**: `002-signal-quality` | **Date**: 2026-11-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-signal-quality/spec.md`

## Summary

For every second of a live or recorded session, MuFuse says which signal can be trusted and, when it cannot, why.
A new package `mufuse.quality` cuts the streams into stretches of one second on sample time and gives each stretch
one answer: a contact state per sensor, coverage, an eye mark, a tension level and mark, a movement mark, and "clean
or not clean" with every reason. The contact grade of feature 001 (`acquisition/contact.py`) is reused unchanged; its
3-second hold is now counted in stretches, not on the wall clock, so a replay gives the same answer as the live run.
Blinks come from a causal 1-10 Hz envelope on AF7 and AF8, tension from the 30-98 Hz spectrum of the same two
sensors, movement from the gyroscope and accelerometer. No detector reads TP9 or TP10. The live view shows the
answer, `mufuse inspect` prints a quality summary, and a guided labelled session plus a scorer prove the 90% gate.

## Technical Context

**Language/Version**: Python 3.15 (CI 3.15.2)

**Primary Dependencies**: numpy 2.5, scipy 1.18 (`signal.butter`, `sosfilt`), typer, rich. No new runtime
dependency.

**Storage**: none new. Answers are computed from the raw recording on demand. Cue times of a labelled session are
ordinary system markers in the existing `markers.jsonl` (format version stays 1). One simulator-made reference
recording (about 1 MB) and its expected answers live in `tests/data/quality_reference/`.

**Testing**: pytest (unit, integration, `hardware` marker), `FakeClock`, simulator with a scripted wearer, a golden
answers file with numeric tolerances, pyright strict, ruff.

**Target Platform**: Windows 11 (the user's machine); CI on ubuntu-latest and windows-latest.

**Project Type**: library + CLI (single package `mufuse`).

**Performance Goals**: quality summary of a 60-minute recording in under 30 s (SC-007); judging adds under 5 ms of
work per second of signal in the live loop; live view updates at least once a second (SC-008).

**Constraints**: every rule is causal (an answer comes 0.25 s after its stretch ends) and depends on sample data only, never on chunk boundaries, arrival order or
the wall clock (FR-012); nothing for AF7, AF8 or any mark may read TP9 or TP10 (FR-006); no network access in the
package (FR-024); P0 and H8 of feature 001 are not touched; coverage stays at 80% or above.

**Scale/Scope**: one user, one headband; sessions up to a few hours (3 600 stretches per hour); about 1 200 new
lines of source in 9 modules, 3 CLI additions, 1 script.

## Constitution Check

*GATE: checked before Phase 0 research and again after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I Local-first privacy | ✅ | All judging is local. The package has no network code; the only download is the public set, by a separate script the user runs, and it sends none of the user's data. Labelled sessions are personal recordings and stay in `recordings/` (git-ignored); their cue times sit inside the recording and are deleted with it. |
| II Describe, don't label | ✅ | Every text names a sensor or a signal ("AF7 is not touching skin", "muscle activity in the signal"). A test walks every user-facing string of the feature against a list of person-state words (SC-009). |
| III Not a medical device | ✅ | No health statement. Tension is shown as a disturbance of the signal (FR-019). |
| IV Signal integrity | ✅ | `RULES_VERSION` on every answer, summary and score report. A stored reference recording with a golden answers file and stated tolerances guards every rule change (FR-025). The reference in the repo is synthetic, because real recordings are personal and the repo is public; the real reference is the user's gate sitting, kept locally and re-scored with `mufuse quality score` whenever the rules change. This feature is the "quality below threshold" gate that principle IV asks for; the quality state is always reported, also when it is "unknown". |
| V Evidence-tiered interpreters | n/a | No interpreter in this feature. |
| VI Two-speed loop | ✅ | Deterministic rules only, no LLM. One answer per second fits the fast loop. |
| VII Test-first quality | ✅ | Tasks are test-first. The simulator gains every fault and event of FR-023, so the full gate runs in CI without a headband. |
| VIII Portable core contract | ✅ | `contracts/quality-rules.md` states rules v1 exactly, and the golden answers file is the reference output a port must reproduce. The recording format is unchanged. |
| IX Simplicity | ✅ | Classical rules with fixed limits, no model, no personal baseline (that is feature 003). Three candidate libraries were rejected in the survey. |

Post-design re-check: ✅ no violations; Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-signal-quality/
├── plan.md              # this file
├── research.md          # Phase 0: decisions R1-R16
├── data-model.md        # Phase 1: entities and state rules
├── quickstart.md        # Phase 1: how to validate, simulator and headband
├── contracts/
│   ├── quality-rules.md      # rules v1, exact, for tests and for a port
│   ├── quality-interface.md  # what later features import and read
│   ├── cli.md                # CLI additions
│   └── labelled-session.md   # cue schedule, marker labels, score report
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/mufuse/
├── quality/                     # NEW
│   ├── __init__.py              # public names: QualityEngine, judge, summarize, RULES_VERSION
│   ├── rules.py                 # RULES_VERSION and every limit, in one frozen dataclass
│   ├── answer.py                # ContactState, Blink, Span, QualityAnswer, SessionQuality, to_json
│   ├── stretch.py               # cuts streams into 1 s stretches on sample time; gaps; watermark rule
│   ├── blink.py                 # causal 1-10 Hz envelope, blink events and the eye mark
│   ├── tension.py               # 30-98 Hz band level per stretch, lines left out
│   ├── motion.py                # gyroscope and accelerometer limits per stretch
│   ├── engine.py                # QualityEngine.feed(chunks); judge(session)
│   ├── summary.py               # QualitySummary from a SessionQuality
│   ├── labelled.py              # cue schedule, rehearsal wearer, scorer, ScoreReport
│   └── public_set.py            # reads the public Muse 2 set from a local folder
├── acquisition/
│   ├── contact.py               # grade_window, mains_share, Reading stay; ContactTracker is retired
│   └── simulated.py             # Wearer gains noisy, flat, railed, turns; clench also on AF7/AF8
├── live_view.py                 # LiveStats feeds the engine; panel shows coverage, blinks, tension, movement
└── cli.py                       # inspect prints the summary; new group `mufuse quality label|score`

scripts/
├── fetch_muse2_set.py           # NEW: download or verify the public set, outside the repo
└── make_quality_reference.py    # NEW: regenerate tests/data/quality_reference from the simulator

tests/
├── data/quality_reference/      # NEW: simulator-made session + answers.json (golden)
├── unit/                        # test_quality_{stretch,contact,blink,tension,motion,engine,summary,
│                                #   labelled,public_set,wording}.py, test_simulated.py (extended)
├── integration/                 # test_quality_replay.py (SC-005), test_quality_ears.py (SC-006),
│                                #   test_quality_cli.py, test_quality_gate.py (rehearsed gate), speed tests
└── hardware/                    # README gains the 002 sitting; no new automated hardware test
```

**Structure Decision**: one new subpackage `mufuse.quality` beside `acquisition` and `recording`. It imports from
both and neither imports from it, except `live_view.py` and `cli.py`, which sit above all three. The per-window
contact grade stays in `acquisition/contact.py` because `acceptance.py` (P0, H8) shares its limits through
`signal_check.py`; those two files are not edited.

## Build order

1. Rules, types, stretch cutter (no signal knowledge; pure bookkeeping). Tests first.
2. Simulator faults and events (FR-023). Keeps `test_rehearsal.py` green: P0 and H8 rehearsals must not change.
3. Contact per stretch with the hold counted in stretches; coverage. Delivers US1 in the library.
4. Motion, tension, blink detectors. Delivers US2 in the library.
5. Engine, combined answer, `judge(session)`, replay and ear-independence tests. Delivers US4.
6. Live view panel and `inspect` summary. Delivers US1 and US3 on screen.
7. Reference recording and golden answers (FR-025).
8. Labelled session, scorer, rehearsed gate in CI; public-set reader and fetch script. Delivers US5.
9. Limits tuned on recordings that already exist locally and on the public set, then frozen as rules v1.
10. The one headband sitting (the user runs it); score report numbers go into the pull request.

## Risks

| Risk | What happens then |
|---|---|
| A jaw clench is too weak on AF7 and AF8 to reach 90% | Reported as a fail of SC-001. The spec is revisited; the limit is not lowered (spec, Assumptions). |
| Limits tuned and scored on the same recording | Limits are frozen (rules v1) before the gate sitting is recorded. The score report states the rules version and that order. |
| figshare refuses a scripted download (it answered 403 to a plain request on 2026-11-26) | `fetch_muse2_set.py` then verifies a copy the user downloaded in the browser, by the published checksums. |
| The public set's file layout differs from what the reader expects | `public_set.py` is written against the downloaded files in step 8; SC-003 is reported as "not scored" with the reason, never as a pass. |
| The simulator's new clench on the forehead changes the H8 rehearsal | The H8 rules are not edited. If the rehearsal changes, the simulator amplitude is corrected, not the check. |

## Complexity Tracking

None.
