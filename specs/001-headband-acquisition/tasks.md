# Tasks: Headband Acquisition & Recording

Legend: `[P]` = parallelizable · `[US#]` = user story · Test tasks precede their implementation (TDD).

## Phase 1 — Setup
- [x] T001 uv project, deps (brainflow, numpy, scipy), dev deps (pytest, pytest-cov, ruff, pyright, pre-commit)
- [x] T002 ruff / pyright / pytest / coverage config in `pyproject.toml`; `.pre-commit-config.yaml`
- [x] T003 GitHub Actions CI (ubuntu + windows, simulated only)
- [x] T004 Add runtime deps: bleak, typer, rich, platformdirs

## Phase 2 — Foundational (blocks all stories)
- [x] T005 [P] Tests for `acquisition/types.py` (Chunk validation) → implement
- [x] T006 [P] Tests asserting `acquisition/athena.py` layout matches BrainFlow `get_board_descr` for all 3 presets → implement
- [x] T007 `acquisition/source.py` HeadbandSource Protocol

## Phase 3 — US3 Develop without headband (P1) 🎯 enables CI for everything else
- [x] T008 [US3] Tests: simulated source shapes, rates, monotonic timestamps, determinism, dropout injection → `simulated.py`
- [x] T009 [US3] Tests: playback reproduces a recorded session exactly → `playback.py` (after T012)

## Phase 4 — US2 Record a labelled session (P1)
- [x] T010 [US2] Tests: manifest schema + session id → `recording/format.py`
- [x] T011 [US2] Tests: writer append/flush, markers, gaps, finalize, completeness → `recording/writer.py`
- [x] T012 [US2] Tests: reader round trip; truncated trailing row; unfinalized session → `recording/reader.py`
- [x] T013 [US2] Integration: simulated → writer → reader (markers within ±1 sample)

## Phase 5 — US1 Connect and see live signal (P1)
- [x] T014 [US1] Tests: `signal_check.classify_channel` (flat / railed / noisy / ok) → implement (thresholds tuned from guided test step 5)
- [x] T015 [US1] `config.py` last-device persistence (tests with tmp dir)
- [ ] T016 [US1] **(code done; needs hardware run: guided test step 1)** `discovery.py` bleak scan (hardware test only)
- [ ] T017 [US1] **(code done; needs hardware run: guided test step 3)** `brainflow_athena.py` real driver (hardware test: 30 s stream, all streams non-empty). 2026-11-25 run after the retiming fix: connect 4.6 s; EEG 102.1%, motion 102.3%, optics 101.8%
- [x] T018 [US1] CLI `stream`, `devices`, `inspect` + rich live view (CliRunner tests with sim source)

## Phase 6 — US4 Survive dropouts (P2)
- [x] T019 [US4] Tests with fake clock: stall after 3 s, backoff 1/2/4/8 s, gap open/close → `supervisor.py`
- [x] T020 [US4] Wire supervisor into `record`; integration test with simulated dropout

## Phase 7 — US5 Preset choice (P3)
- [x] T021 [US5] Preset validation (invalid → exit 2 with list); optics column count follows preset

## Phase 8 — Polish
- [x] T022 CLI `record` with key markers; Ctrl+C finalization test
- [ ] T023 Hardware acceptance run: `uv run mufuse hardware-test`, paste `report.md` into the PR **(guided test ready; needs hardware run)**
- [x] T024 README quickstart
- [ ] T025 Record headband firmware version in the manifest (fNIRS research: firmware changed optics channel behavior) **(code done: BLE "v6" query before BrainFlow connects; needs hardware run: guided test step 2)**
- [x] T026 Retime BrainFlow arrival timestamps instead of dropping duplicates (`timing.py`)
- [x] T027 Guided hardware test `mufuse hardware-test`: on-screen directions, automatic grading against SC-001…SC-005, report; dry run with a simulated headband and person in CI
