<!--
Sync Impact Report
- Version change: 1.0.0 → 1.1.0 (MINOR: Principle V materially expanded)
- Principles changed: V gains opt-in early feedback. An interpreter still in shadow mode may
  be surfaced when the user switches early feedback on, always tagged as unproven.
- Rationale: the user wants the companion to speak early and be refined in use. Descriptions
  and check-ins were already allowed; only interpretations were held back. Default behaviour,
  hit-rate tracking and the random-prompt share are unchanged.
- Sections added or removed: none
- Templates requiring updates: none (plan/spec/tasks templates read this file at runtime)
- Specs affected: none yet (001 has no interpreters); 006 and 007 must implement the tag.
- Sources: docs/design/2026-11-26-companion-experience.md
- Earlier: template → 1.0.0 (2026-11-25, initial ratification, Principles I–IX)
-->
# MuFuse Constitution

## Core Principles

### I. Local-First Neural Privacy (NON-NEGOTIABLE)
- Raw biosignals (EEG, optics, IMU) and inferred mental states MUST stay on the user's own
  devices by default. Inferred states are protected as strictly as raw neural data.
- Any network egress (cloud LLM, sync, telemetry) MUST be opt-in per feature, MUST send
  summaries only (never raw signal), and MUST be visible in the UI when active.
- Every stored artifact MUST be deletable by the user in one action, including derived data.

Rationale: neural data is legally sensitive (CO, CA, MT, CT neural-data laws; Chile v. Emotiv)
and ethically more sensitive than most personal data.

### II. Describe, Don't Label
- The system MUST describe signal changes relative to the user's own baseline ("heart rate
  +8 bpm vs. your morning baseline, blinks up"), not assert mental states ("you are anxious").
- Every interpretation MUST be presented as a hypothesis with an evidence tier and confidence,
  and MUST invite the user's own account. The user's self-report always overrides the model.
- Mind-reading, diagnostic, or clinical language MUST be blocked by a deterministic output
  filter before any text or speech reaches the user.

Rationale: no validated scalp marker exists for anxiety, rumination, or spontaneous craving;
labels create nocebo effects and probe-wording bias.

### III. Not a Medical Device; Safety Is Deterministic
- MuFuse is a self-awareness and journaling tool. It MUST NOT diagnose, treat, or claim
  clinical efficacy, and MUST NOT present itself as therapy.
- Crisis handling (self-harm, suicidal ideation, acute danger) MUST be a pre-written,
  non-LLM path triggered by a deterministic detector, providing crisis resources (e.g., 988).
  The LLM MUST NOT be able to override, rephrase, or suppress it.
- Features that could reinforce rumination or dependence MUST have a stop/snooze path.

### IV. Signal Integrity Is Versioned and Regression-Tested
- Filters, feature definitions, and model artifacts MUST be versioned. Every derived record
  MUST carry the versions that produced it.
- Any change to signal processing MUST pass regression tests against stored reference
  recordings (synthetic + real golden files) with documented numeric tolerances.
- No inference may be emitted when signal quality (contact, motion, EMG/EOG contamination)
  is below threshold; the quality state itself is always reported.

### V. Evidence-Tiered, Self-Validating Interpretations
- Interpretations are plug-ins (declarative manifest + scoring function), each declaring an
  evidence tier (Grounded / Extrapolated / Speculative), required signals, quality gates,
  and approved phrasing.
- A share of experience-sampling prompts (default 30–50%) MUST be randomized, independent of
  detectors, so each interpreter's personal hit rate can be compared against chance.
- New interpreters MUST start in shadow mode (logged, not surfaced) and MAY be promoted only
  when they beat the random-prompt base rate on the user's own data; they are demoted when
  they stop doing so. Self-initiated labels (ring presses) are stored separately and never
  pooled with random-probe labels for hit-rate computation.
- Early feedback is opt-in. The user MAY switch it on, for one interpreter or for all; an
  interpreter in shadow mode is then surfaced, and every statement it makes MUST carry the
  tag "speculative · unproven for you". Early feedback MUST be off by default and MUST be
  switchable off in one action. It MUST NOT change hit-rate tracking or the random-prompt
  share, and it never relaxes Principles II, III or IV. Only promotion removes the tag.

### VI. Two-Speed Loop
- Fast loop (< 1 s): deterministic features + rules → non-verbal cue (haptic/tone). The LLM
  MUST NOT be in the fast path.
- Slow loop: the LLM receives structured, quality-flagged summaries — never raw signal — and
  produces probes, journal entries, and reflections. Numbers and statistics MUST be computed
  by code, not estimated by the LLM.

### VII. Test-First Quality
- Behavior changes MUST be developed test-first (red → green → refactor).
- Hardware-dependent code MUST sit behind an interface with a synthetic implementation
  (BrainFlow SYNTHETIC_BOARD or recorded-file playback) so the full pipeline runs in CI
  without a headband. Hardware tests are marked and run manually.
- Lint, format, type-check, and tests MUST pass before merge.

### VIII. Portable Core Contract
- The interface between Python research (Phase 0) and the app (Phase 1+) is: feature
  definitions (spec + reference outputs), ONNX model artifacts, and the recording format.
  Any port MUST reproduce reference outputs within tolerance.

### IX. Simplicity and Honest Scope
- Prefer classical features + personal calibration over large models unless a model beats
  the classical baseline on the user's data. Start with the smallest thing that works (YAGNI).
- Experimental sensors (e.g., fNIRS hemoglobin) ship behind an "experimental" flag until
  they pass their validation protocol.

## Signal & Platform Constraints

- Device: Muse S Athena. EEG TP9, AF7, AF8, TP10 @ 256 Hz (DEFAULT preset); accel/gyro
  @ 52 Hz (AUXILIARY); raw optics 4/8/16 ch + battery @ 64 Hz (ANCILLARY).
- Acquisition (Phase 0): Python ≥ 3.12, BrainFlow ≥ 5.22 native BLE on Windows 10.0.19041+.
  Board ID name MUST be resolved from the installed enum (ATHENA vs ANTHENA spelling).
- Only one central may connect to the headband at a time; the app owns one hub per session.
- Speech: offline (sherpa-onnx VAD/STT/TTS). LLM: local (Ollama on desktop; on-device on
  phone). Realtime cloud speech APIs are out of scope by default.
- App (Phase 1+): Flutter; classifiers via ONNX Runtime.
- Connection UX: auto-reconnect to last headband, per-electrode contact indicator, no manual
  OS pairing steps.

## Development Workflow & Quality Gates

- Each feature follows Spec Kit: specify → (clarify) → plan → tasks → (analyze) → implement,
  on its own numbered branch.
- Python tooling: uv (env/lock), ruff (lint + format), pyright (types, strict on `src/`),
  pytest (+ coverage ≥ 80% on non-hardware modules), pre-commit hooks.
- CI (GitHub Actions) runs lint, types, and tests on every push and PR using synthetic data.
- Golden recordings live in `tests/data/` (small) or are fetched by checksum (large); never
  commit personal recordings to the public repo.
- Every plan MUST include a Constitution Check against Principles I–IX.

## Governance

- This constitution supersedes other practices. Amendments require a PR that updates this
  file, states the semantic version bump and rationale, and notes impact on templates/specs.
- Versioning: MAJOR = principle removed/redefined; MINOR = principle/section added or
  materially expanded; PATCH = clarifications.
- Reviews and `/speckit-analyze` runs MUST verify compliance; violations require an explicit,
  documented justification in the plan's Complexity Tracking section.

**Version**: 1.1.0 | **Ratified**: 2026-11-25 | **Last Amended**: 2026-11-26
