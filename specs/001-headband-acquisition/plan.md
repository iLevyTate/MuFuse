# Implementation Plan: Headband Acquisition & Recording

**Branch**: `001-headband-acquisition` | **Date**: 2026-11-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-headband-acquisition/spec.md`

## Summary

Build the acquisition layer every later MuFuse feature stands on: a `HeadbandSource` interface with three
implementations (BrainFlow Muse S Athena, deterministic simulated Athena, recorded-session playback), a stall-detecting
supervisor that reconnects and records gaps, a crash-safe append-only session recorder (per-stream little-endian float64
binary + JSON manifest + JSONL markers/gaps), and a CLI (`devices`, `stream`, `record`, `inspect`) with a live terminal
view. Everything except the real-device driver is covered by hardware-free tests in CI.

## Technical Context

**Language/Version**: Python 3.13 (uv-managed)

**Primary Dependencies**: brainflow 5.24 (driver, board id 67 `MUSE_S_ATHENA_BOARD`), numpy, bleak (BLE scan for
`devices`), typer (CLI), rich (live view), platformdirs (config location)

**Storage**: local files — one folder per session under `recordings/` (git-ignored); format in
[contracts/recording-format.md](./contracts/recording-format.md)

**Testing**: pytest + pytest-cov; `hardware` marker for real-device tests; fake clock for supervisor tests

**Target Platform**: Windows 11 (native BLE, build ≥ 10.0.19041); CI on ubuntu + windows with simulated source

**Project Type**: Python library + CLI (single project)

**Performance Goals**: sustain EEG 256 Hz × 8 rows + IMU 52 Hz × 6 + optics 64 Hz × 16 with poll loop at 20 Hz; < 5% CPU;
display refresh 4 Hz

**Constraints**: offline only (FR-013); recordings readable after crash at any instant (FR-008); no interpolation over gaps

**Scale/Scope**: single user, sessions up to ~8 h (~ 60 MB EEG float64/h per 8 rows → acceptable)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I Local-first privacy | ✅ | Files only on local disk, no network code except BLE; recordings git-ignored |
| II Describe, don't label | n/a | No interpretations in this feature |
| III Not medical / safety | n/a | No user-facing interpretation |
| IV Signal integrity versioned | ✅ | Manifest stores format version, software version, driver version, preset; gaps explicit, never interpolated |
| V Evidence-tiered interpreters | n/a | — |
| VI Two-speed loop | ✅ | Acquisition is deterministic, no LLM |
| VII Test-first quality | ✅ | Source interface + simulated + playback; TDD; CI on two OSes; `hardware` marker |
| VIII Portable core contract | ✅ | Recording format is a documented contract readable from Dart (raw LE float64 + JSON) |
| IX Simplicity | ✅ | Single poll thread; no async framework; no database |

Post-design re-check: ✅ no violations; Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-headband-acquisition/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── source-interface.md
│   ├── recording-format.md
│   └── cli.md
└── tasks.md
```

### Source Code (repository root)

```text
src/mufuse/
├── __init__.py
├── cli.py                      # typer app: devices / stream / record / inspect
├── config.py                   # last-device persistence (platformdirs)
├── acquisition/
│   ├── __init__.py
│   ├── types.py                # StreamKind, StreamSpec, Chunk, DeviceInfo, SourceError
│   ├── athena.py               # Athena layout constants + presets (mirrors BrainFlow descr)
│   ├── source.py               # HeadbandSource Protocol
│   ├── simulated.py            # deterministic Athena-shaped synthetic source
│   ├── playback.py             # replays a recorded session
│   ├── brainflow_athena.py     # real driver (hardware; excluded from coverage)
│   ├── discovery.py            # bleak scan for Muse devices
│   ├── supervisor.py           # stall detection, reconnect backoff, gap events
│   └── signal_check.py         # rough per-channel indicator (flat / railed / noisy / ok)
└── recording/
    ├── __init__.py
    ├── format.py               # manifest schema + FORMAT_VERSION
    ├── writer.py               # append-only, crash-safe
    └── reader.py               # load session → aligned arrays

tests/
├── unit/                       # types, athena layout, simulated, signal_check, supervisor, format
├── integration/                # simulated → writer → reader round trip; playback; CLI via CliRunner
└── hardware/                   # @pytest.mark.hardware real-headband tests
```

**Structure Decision**: single Python package `mufuse` with `acquisition` and `recording` subpackages; tests split by
unit / integration / hardware.

## Complexity Tracking

None.
