# MuFuse — guidance for Claude

Local-first tools for the Muse S Athena headband. Not a medical device.
This repository is the research rig (acquisition, signal quality, signal research): a tool for others
to check attachment, calibrate on their own head and develop on, not the end product. The app plans in
`docs/ROADMAP.md` stay and may move to their own repository later.
Rules that override everything else here: `.specify/memory/constitution.md`.

## Commands
```bash
uv sync                                   # install
uv run ruff format && uv run ruff check   # format + lint
uv run pyright                            # strict types on src/
uv run pytest -m "not hardware"           # CI suite (no headband)
uv run pytest -m hardware -s              # needs headband on, Muse app closed
uv run mufuse stream --source sim         # live view without hardware
uv run python scripts/hw_acceptance.py             # every hardware check in one sitting
uv run python scripts/hw_acceptance.py --rehearse  # the same on the simulator, no headband
uv run mufuse quality label --source sim           # the 002 labelled session, simulated (9.5 min)
uv run python scripts/make_quality_reference.py    # after a meant rules change; raise RULES_VERSION
uv run python scripts/make_features_reference.py   # after a meant features change; raise FEATURES_VERSION
MUFUSE_SIM_WEARER=resting uv run mufuse record --source sim --duration 120   # data for `features`
```

## Workflow
- Each feature gets one design note, `specs/NNN-name/README.md` (goal, gate, decisions, open
  questions, done list, Constitution Check); full Spec Kit only where a wrong output can harm a
  person (007's crisis path). 001 and 002 keep their Spec Kit files. Roadmap: `docs/ROADMAP.md`.
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
- `quality/` — feature 002: `engine.py` judges each 1 s stretch (contact, coverage, eye, tension,
  movement) from samples only, the same live and replayed; `labelled.py` the cued session and
  scorer; `public_set.py` the Muse 2 set. Rules: `specs/002-signal-quality/contracts/quality-rules.md`.
- `features/` — feature 003: `engine.py` makes one frame per judged second (exponent, alpha
  peak, band shares, blink rate, HR, RMSSD, z-scores vs a rolling personal baseline), the same
  live and replayed; constants in `params.py` (`FEATURES_VERSION`); golden frames in
  `tests/data/features_reference/` (`scripts/make_features_reference.py`).
- `companion/` — feature 005: `store.py` (SQLite in the user data folder: sessions, check-ins by
  source, marks), `scheduler.py` (random check-ins ≥ 30%, 15 min spacing, quiet times),
  `describe.py` (the baseline line, words for the signal only), `serve.py` (`Engine` + `Server`:
  127.0.0.1, per-run token in `serve.json`, SSE `/events`, `POST /command`; message examples in
  `tests/data/serve_messages/`).
- `observe/` — feature 006: `observations.py` (15 s median z ≥ 2 starts, < 1 ends), `interpreters.py`
  (TOML manifests in `manifests/`, first-party `REGISTRY`, `attention_drift`), `evaluate.py` (random
  check-ins only, AUC, permutation shuffled within days, fixed looks), `ledger.py` (standing, early
  feedback). Scores of every check-in are kept (shadow mode); insights only when promoted or opted in.
- `chat/` — feature 007: `crisis.py` (fixed reply, US 988 first), `filter.py` (blocks statements about
  the person, conditions, diagnosis, treatment, accuracy claims, mind reading), `summary.py` (numbers
  from code, template answer), `models.py` (Ollama default; Claude opt-in via the `cloud` extra,
  `claude-opus-5-5`, fallbacks on), `session.py`, `client.py`. Never let a model bypass filter or crisis.
- `journal/` — feature 008: `timeline.py`, `patterns.py` (random check-ins only; n ≥ 3; every pattern
  shows n, effect in points and "hypothesis"), `calendar.py` (stdlib .ics, meetings), `review.py`
  (static escaped HTML in the user data folder).
- `cli.py` — `devices / stream / record / inspect / features / serve / chat / timeline / journal /
  calendar / review / interpreters / quality`; `banner.py` — header shown only on a TTY.

## Gotchas
- Only one device can connect to the headband; the phone Muse app must be closed.
- Never commit personal recordings (`recordings/` is git-ignored); the repo is public.
- Inject clocks (`tests/conftest.py::FakeClock`) for anything time-dependent.
- fNIRS hemoglobin is experimental until feature 004's validation passes. BrainFlow optics rows are
  in wire order (OPT1-4 red, 5-8 ambient, 9-12 730 nm, 13-16 850 nm), not Mind Monitor's order;
  guided check F1 confirms it per unit (see `docs/research/2026-11-25-athena-fnirs-resources.md`).
- Ear sensors (TP9, TP10) are not reliable until issue #12 is fixed: draw no conclusion from
  them, never loosen P0 or H8 for it, and keep features working on AF7/AF8 alone
  (`docs/KNOWN-ISSUES.md`).
- User-facing language: describe signal changes vs. personal baseline; never "you are anxious".
- Brand tokens, logo rules and the InteraXon notice: `docs/BRAND.md`. Status colours grade
  signal quality only, never the person.
