# MuFuse
Punk EEG.

A local-first self-awareness companion for the **Muse S Athena** headband: stream and record
EEG, motion and optics on your own machine, then (later milestones) learn your personal
signals, ask good questions at the right moments, and keep a journal. Not a medical device.

- Rules: [`.specify/memory/constitution.md`](.specify/memory/constitution.md)
- Plan: [`docs/ROADMAP.md`](docs/ROADMAP.md)
- Evidence: [`reports/`](reports/) and [`docs/research/`](docs/research/)

## Setup

Requires Windows 10 (build 19041+) or 11 with Bluetooth, and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run mufuse stream --source sim     # works without a headband
```

## Connecting the Muse S Athena

No Windows pairing is needed. The headband advertises over Bluetooth LE and MuFuse connects
directly. If you previously paired it in Windows settings, remove it there first.

1. Close the Muse app on your phone (or turn phone Bluetooth off). Only one device can be
   connected to the headband at a time.
2. Turn the headband on. Moving or blinking lights mean it is waiting for a connection.
3. `uv run mufuse devices` should list something like `MuseS-XXXX`.
4. Put it on: hair away from the forehead sensors, behind-ear sensors on skin. Slightly
   dampening the sensors helps.
5. `uv run mufuse stream`. The first run scans and remembers your headband. Within about 15 s
   the EEG row should read `ok` for TP9, AF7, AF8, TP10 at roughly 256/52/64 Hz. Press `q` to quit.

Not found? Power-cycle the headband, toggle Windows Bluetooth, make sure the phone isn't
connected, and stay within about 2 m.

## Recording

```bash
uv run mufuse record --notes "deep work" --duration 600
uv run mufuse inspect recordings/<session_id>
```

While recording: `space` drops a moment marker, `1`–`9` start/end numbered blocks, `q` stops.
Recordings stay in `recordings/` on your machine (git-ignored) in an open format described in
[`specs/001-headband-acquisition/contracts/recording-format.md`](specs/001-headband-acquisition/contracts/recording-format.md).

## Development

```bash
uv run ruff format && uv run ruff check && uv run pyright
uv run pytest -m "not hardware"       # CI suite, no headband needed
uv run pytest -m hardware -s          # with the headband on (see tests/hardware/README.md)
```

Features are built with [Spec Kit](https://github.com/github/spec-kit) (`/speckit-specify` →
`/speckit-plan` → `/speckit-tasks` → `/speckit-implement`), test-first, one branch per feature.
