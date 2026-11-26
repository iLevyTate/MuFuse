# MuFuse — guidance for Claude

Local-first self-awareness companion for the Muse S Athena headband. Not a medical device.
Rules that override everything else here: `.specify/memory/constitution.md`.

## Commands
```bash
uv sync                                   # install
uv run ruff format && uv run ruff check   # format + lint
uv run pyright                            # strict types on src/
uv run pytest -m "not hardware"           # CI suite (no headband)
uv run pytest -m hardware -s              # needs headband on, Muse app closed
uv run mufuse stream --source sim         # live view without hardware
```

## Workflow
- Features go through Spec Kit: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`.
  Specs live in `specs/NNN-name/`; roadmap in `docs/ROADMAP.md`.
- Test-first. One branch per feature; PR to `main`; merge only when CI (ubuntu + windows) is green.
- Coverage gate 80% (hardware-only modules `brainflow_athena.py`, `discovery.py` are excluded).

## Architecture (src/mufuse)
- `acquisition/source.py` — `HeadbandSource` protocol; implementations: `brainflow_athena.py` (real,
  BrainFlow board 67), `simulated.py` (deterministic, CI), `playback.py` (recorded sessions).
- `acquisition/athena.py` — stream layout; a test asserts it matches installed BrainFlow descriptors.
- `acquisition/timing.py` — `Retimer`: BrainFlow stamps arrival time (~24% duplicate EEG stamps);
  never drop samples, retime them. Gaps > 0.25 s are preserved.
- `acquisition/supervisor.py` — stall (3 s) detection, backoff reconnect, explicit gaps.
- `recording/` — append-only float64 LE files + JSON manifest + JSONL markers/gaps (crash-safe).
- `cli.py` — `devices / stream / record / inspect`.

## Gotchas
- Only one device can connect to the headband; the phone Muse app must be closed.
- Never commit personal recordings (`recordings/` is git-ignored); the repo is public.
- Inject clocks (`tests/conftest.py::FakeClock`) for anything time-dependent.
- fNIRS hemoglobin is experimental until feature 004's validation passes; channel order is unverified
  (see `docs/research/2026-11-25-athena-fnirs-resources.md`).
- User-facing language: describe signal changes vs. personal baseline; never "you are anxious".
