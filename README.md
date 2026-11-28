<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/mufuse-banner-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="assets/mufuse-banner-light.svg">
    <img alt="MuFuse: Punk EEG." src="assets/mufuse-banner-light.svg" width="520">
  </picture>
</p>

> **Punk EEG.** Local-first, open-source tools for the Muse S Athena headband: check that it sits
> right, check how far its signals can be trusted on your own head, and build on that.

## What this repository is

The **research rig**. It is a tool for anyone with a Muse S Athena, not the end product:

- **Check the attachment.** The live view grades the contact of every sensor each second and says
  how much of the head is covered. A preflight check judges the fit before anything else runs.
- **Calibrate on your own head and your own unit.** One guided sitting checks the headband itself
  (rates, sample loss, battery, the order of the optics rows). A second guided session cues blinks,
  jaw clenches, head turns and sensor lifts, and scores how many of them the quality marks find.
- **Develop on it.** One `HeadbandSource` interface with a real headband, a deterministic
  simulator and playback of recorded sessions; an open recording format; quality answers that are
  the same live and replayed. Every test except the hardware ones runs without a headband.

Everything stays on your machine. Recordings are never uploaded and never enter the repository.

## What it is not

- Not the end product. The companion below is planned, not built.
- Not mind reading. It can't see your thoughts.
- Not a mental-state labeller. It never tells you "you are anxious".
- Not a medical device, diagnosis or therapy, and not a replacement for professional care.

## Where it is going

The rig is the ground for a companion that **describes** signal changes against *your* baseline
("heart rate up, blinks doubled vs this morning") and asks what was going on. You name it; it
learns from your answers, and every interpretation says how strong the science is and how often
it has been right for you. That app (desk strip, chat, phone) stays planned in
[`docs/ROADMAP.md`](docs/ROADMAP.md); it may move to a repository of its own later, built on this
one. Nothing of those plans is dropped.

## Status

**001 acquisition** is shipped: connect, stream, auto-reconnect, crash-safe recording with
markers. **002 signal quality** is built. Its limits were checked on the headband and frozen as
rules v1 on 2026-11-27; the one sitting that decides its gate is still to be recorded. What the
marks find, and what they do not find yet, is in [`docs/KNOWN-ISSUES.md`](docs/KNOWN-ISSUES.md).

| Command | What it does |
|---|---|
| `mufuse devices` | Scan for nearby Muse headbands |
| `mufuse stream` | Live signal view with contact, coverage, blinks, muscle activity and head movement (`--source sim` works without a headband) |
| `mufuse record` | Record a session with keyboard markers |
| `mufuse inspect` | Summarize a recorded session, ending with its signal quality |
| `mufuse quality label` | Check the fit, then record the guided 9.5-minute labelled session (cued blinks, jaw clenches, head turns, sensor lifts) and score it |
| `mufuse quality score` | Score a labelled recording, or the public Muse 2 set with `--public DIR` |
| `mufuse serve` | Run the engine for the desk strip: live quality, features against your baseline, check-ins ("What's on your mind?") stored by source in a local SQLite file; listens on 127.0.0.1 only, with a token made fresh each run |
| `mufuse timeline` / `mufuse journal` / `mufuse calendar import` / `mufuse review` | Look back: a serve session as a timeline, your own notes, meetings from an exported `.ics` file, and a weekly reflection whose patterns each show n, the effect and the word "hypothesis", also written as a review page on disk |
| `mufuse chat` | Ask the running engine what the signal is doing; a local model (Ollama) words the answer, the Claude API only with `--cloud` (summary only, never raw signal; `uv sync --extra cloud`); a fixed filter and crisis path stand in front of every reply |
| `mufuse interpreters` | Each interpreter's standing on your own random check-ins (shadow or promoted, hit rate against the base rate, AUC, p, next look); `feedback on\|off` switches early feedback, tagged "speculative · unproven for you" |
| `mufuse features` | Per-second EEG and pulse features of a recording (aperiodic exponent, alpha peak, band shares, blink rate, heart rate, RMSSD), each against your own baseline; `--csv` writes them out |
| `python scripts/hw_acceptance.py` | Every hardware check of the headband in one guided sitting (`--rehearse` plays it on the simulator) |

Next up: the gate sitting for signal quality, then EEG and heart-rate features, the labelling
loop, experimental fNIRS. See [`docs/ROADMAP.md`](docs/ROADMAP.md).

- Rules: [`.specify/memory/constitution.md`](.specify/memory/constitution.md)
- Brand: [`docs/BRAND.md`](docs/BRAND.md)
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

TP9 or TP10 not reading `ok`? Ear contact is fragile: see `docs/KNOWN-ISSUES.md` for what to
try. Everything in signal quality works on the two forehead sensors alone.

Not found? Power-cycle the headband, toggle Windows Bluetooth, make sure the phone isn't
connected, and stay within about 2 m.

## Checking your own headband

With the headband on and the phone Muse app closed:

```bash
uv run mufuse stream                                   # fit: each sensor should read ok
uv run python scripts/hw_acceptance.py                 # the unit: every hardware check, guided
uv run mufuse quality label --source athena            # your head: 9.5 min of cues, ends with a score
uv run mufuse quality score recordings/<session_id>    # score that recording again later
uv run mufuse features recordings/<session_id> --csv f.csv   # per-second features (003)
```

Without a headband, `scripts/hw_acceptance.py --rehearse` and `mufuse quality label --source sim`
play the same sittings on the simulator. What each check asks of you and how it is judged:
[`tests/hardware/README.md`](tests/hardware/README.md). The quality limits were checked on one
person and one headband, so a score from your own head is the number that counts for you.

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

Each feature is planned in one design note (`specs/NNN-name/README.md`) and built test-first,
one branch per feature, merged when CI is green. The first two features used
[Spec Kit](https://github.com/github/spec-kit) in full; it stays available for the risky ones.

---

<sub>MuFuse is an independent, MIT-licensed open-source project and is not affiliated with,
endorsed by, or sponsored by InteraXon Inc. Muse is a trademark of InteraXon Inc. Not an Official
Muse application.</sub>
