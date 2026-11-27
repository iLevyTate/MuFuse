# MuFuse Roadmap

Each milestone is one Spec Kit feature (`specs/NNN-name/`), built test-first, with an exit
**quality gate** that must pass before the next milestone depends on it.
Rules: `.specify/memory/constitution.md`. Evidence: `reports/Muse EEG self awareness research.md`.
Experience design: `docs/design/2026-11-26-companion-experience.md`.
Rows are in build order; feature numbers are names and do not change when the order does.

## Phase 0: Desktop research rig (Python, Alienware)

| # | Feature | Delivers | Quality gate |
|---|---|---|---|
| 000 | **Foundation** | uv project, ruff/pyright/pytest, pre-commit, GitHub Actions CI, `mufuse` package skeleton | CI green on an empty pipeline |
| 001 | **Acquisition & recording** | `HeadbandSource` interface (BrainFlow Athena + synthetic + file playback), all 3 presets (EEG/IMU/optics), auto-reconnect, session recording to disk with event markers, CLI `mufuse devices / stream / record` | Synthetic-board tests in CI; manual hardware test: 10-min recording with < 0.5% dropped samples |
| 002 | **Signal quality** | Per-channel contact, blink/EOG, EMG (jaw) index, IMU motion gate, live quality panel | Labelled artifact test set (blinks, clenches, head turns) detected ≥ 90% |
| 003 | **EEG + PPG features** | Filters, Welch PSD, periodic alpha + aperiodic exponent (fooof), blink rate, HR/RMSSD from optics, rolling personal baseline + z-scores | Reference outputs frozen as golden files; PPG HR within ±3 bpm of a chest strap/phone reference |
| 005 | **Labelling loop** | Event markers (hotkey now, BLE ring later), experience-sampling scheduler with ≥ 30% random prompts, one-tap categories, SQLite store; `mufuse serve` (local API, this PC only) and the Flutter desk strip that shows quality, "now against baseline" and the check-in (may become two specs) | 1 week of real use: ≥ 70% prompt compliance, labels stored separately by source |
| 006 | **Observations + interpreter plug-ins** | Observation layer (neutral deviations), YAML plug-in manifests, shadow mode, opt-in early feedback tagged "speculative · unproven for you", hit-rate vs random base rate, promotion/demotion | First interpreter ("attention drift") evaluated in shadow mode against random probes |
| 004 | **fNIRS pipeline (experimental)**, moved after 006 on 2026-11-26 because no companion goal depends on it — prerequisites in `docs/research/2026-11-25-athena-fnirs-resources.md`: bench-verify the 16-channel order (two competing hypotheses), measure source–detector spacing, use p1041/p1042 (ambient channels), watch the ln-vs-log10 trap | Raw optics → optical density → HbO/HbR (modified Beer–Lambert), pulse/motion correction, short-channel regression if geometry allows | Validation protocol: breath-hold, mental arithmetic and rest blocks show the expected HbO direction and timing in ≥ 70% of blocks across 5 sessions |
| 007 | **Chat + local LLM, then voice** | The strip opens into a chat (text first; sherpa-onnx VAD/STT/TTS after), Ollama by default and a cloud model opt-in with summaries only, "what are you seeing?" (change / reliability / question), cue ladder, describe-don't-label output filter, deterministic crisis path | Output-filter test suite (banned phrasings blocked); crisis path tests; latency of fast-loop cues < 1 s |
| 008 | **Journal & timeline** | Session timeline, voice journal, context tags (calendar, activity), weekly reflection with stats computed in code | Every pattern shown has n, effect and a "hypothesis" label |
| 009 | **Breathing & first exercises** | HRV resonance breathing (~6 breaths/min) with live PPG, defusion and urge-surfing scripts | Breathing session raises RMSSD vs pre-session in the user's own data |

**Phase 0 exit:** at least one interpreter beats the random-prompt hit rate across ≥ 2 weeks; the fNIRS gate is passed or fNIRS stays flagged experimental.

**Open hardware issue (2026-11-26):** the ear sensors (TP9, TP10) do not hold contact, so 001's P0 and H8 checks are still open and 002 and 003 must work on the forehead sensors alone. See `docs/KNOWN-ISSUES.md`.

## Phase 1: App (Flutter, desktop + phone)
010 Dart Athena BLE decoder (matches the Python golden decode) · 011 Dart feature port (matches golden features) · 012 ONNX interpreters · 013 sherpa_onnx speech + on-device LLM · 014 app UX (connect, contact view, timeline, journal; the desk strip and chat arrive earlier, in 005 and 007, on top of the Python engine)

## Phase 2: Phone as hub + wearables
015 Phone-as-hub (Muse BLE + ring HID + bone-conduction audio) · 016 self-experiment engine (n-of-1 trials) · 017 context fusion · 018 CBT/ACT thought-work templates (scripted states, LLM fills the conversation)

Later note, not yet a feature: a craving cue exercise (pictures shown on purpose, averaged brain responses). Spontaneous craving cannot be read from this hardware.
