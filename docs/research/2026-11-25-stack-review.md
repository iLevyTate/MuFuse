# MuFuse: Stack & Architecture Review

_2026-11-25. Input for Spec Kit `/speckit.constitution` and `/speckit.specify`._

## 1. What the hardware can and cannot tell you

**Muse S Athena streams** (per BrainFlow 5.22 docs):

| Stream | Detail | Rate |
|---|---|---|
| EEG | 4 ch: TP9, AF7, AF8, TP10 (dry, behind ears + forehead); 8-ch presets add 4 aux | 256 Hz |
| Optics (fNIRS / PPG raw) | 4, 8 or 16 raw rows depending on preset. **No ready-made PPG**: you derive heart rate/HRV yourself | 64 Hz |
| IMU | accel + gyro, 3 axes each | 52 Hz |
| Battery | 1 row in ancillary preset | 64 Hz |

**Realistically detectable** (with personal calibration):
- Eye blinks / eye movements (AF7/AF8), jaw clench, head motion: very reliable, usable as *input gestures*
- Drowsiness / low arousal (rising theta + alpha, slow eye movements)
- Relaxed vs. engaged (frontal alpha, theta/beta trends)
- Heart rate + HRV from optics (stress/arousal proxy)
- Slow prefrontal oxygenation trends from fNIRS (workload proxy, seconds-scale)
- Mind-wandering: **probabilistic**. Lab studies report 0.50–0.85 accuracy *per person*; alpha power is the strongest marker. Consumer devices are less validated.

**Not detectable:** thought content, "what your unconscious is doing", emotions with any certainty, anything diagnostic.

**Design consequence:** the AI should not claim to read your mind. It should **notice shifts and ask** (experience sampling), then **remember your answers** and find patterns between your self-reports and your physiology over weeks. That is how mind-wandering research works, and it is the product's honest core loop:

> EEG notices a shift → gentle cue → you say what was on your mind → LLM journals it → over time, the model learns *your* signatures.

## 2. Acquisition options (BLE → computer/phone)

| Option | Desktop (Windows) | Android/iOS | Verdict |
|---|---|---|---|
| **BrainFlow 5.22+** (`MUSE_S_ATHENA_BOARD`, native BLE, no dongle) | ✅ Win 10.0.19041+ | ❌ Muse boards not listed for mobile | **Best for Phase 0 prototype** |
| **OpenMuse** (Python, Athena-specific, LSL streaming) | ✅ | ❌ | Fallback if BrainFlow's new Athena support is flaky |
| **muse-rs** (Rust, btleplug, Athena auto-detect, decodes PPG) | ✅ | ⚠️ btleplug mobile support is partial | Good **reference implementation** of the packet format |
| **Pure Dart parser** (flutter_blue_plus, char `273e0013`, tag-decoded) | ✅ | ✅ | **Best for the app** |
| BrainFlow via FFI in Flutter/RN | ✅ | ❌ (no mobile Muse support) | Ruled out for the phone path |

Caveats:
- BrainFlow's blog spells the enum `MUSE_S_ANTHENA_BOARD`, its docs `MUSE_S_ATHENA_BOARD`. Check the installed enum.
- Athena protocol: control char `273e0001-…`, data chars `273e0013-…` / `273e0014-…`; packet tags `0x11/0x12` EEG4/8, `0x34/35/36` Optics4/8/16, `0x47` IMU, `0x88/0x98` battery.
- Start sequence (from BrainFlow): `v6, s, h, <preset>, s` → `dc001` ×2 → `L1` (low latency).
- **Only one device can connect to the Muse at a time.** Pick one hub (PC *or* phone) per session. The official Muse app must be closed.

## 3. Recommended path

### Phase 0: Prove the signal (Python, Alienware, ~2–4 weeks)
The hard part is the signal→state model, not the app. Python has the best EEG ecosystem.

- **Acquisition:** `brainflow>=5.22` (Python)
- **DSP:** BrainFlow `DataFilter` + `scipy` / `mne` (bandpass 1–40 Hz, notch 60 Hz, Welch PSD, band powers)
- **Recording:** raw data + event markers to Parquet (or XDF via LSL if using OpenMuse)
- **Calibration protocol:** eyes-closed rest, focused task (e.g., n-back), free mind-wandering, random thought probes ("were you on task?")
- **Classifier:** start with logistic regression/LDA on band-power features per person; export to **ONNX**
- **LLM:** Ollama + a 7–14B instruct model, local
- **Speech:** `sherpa-onnx` (VAD + STT + TTS, offline). Chosen because the *same library* has Flutter bindings for Phase 1

**Exit criteria:** your personal classifier beats chance meaningfully on held-out sessions, and the probe loop feels useful.

### Phase 1: The app (Flutter, desktop + phone, one codebase)
- **UI + BLE:** Flutter + `flutter_blue_plus`, pure-Dart Athena parser (use muse-rs/OpenMuse decoders as the spec)
- **DSP:** Dart (256 Hz × 4 ch is light; port the exact Phase 0 feature code and test it against Phase 0 recordings)
- **Classifier:** ONNX Runtime (model trained in Python, unchanged)
- **Speech:** `sherpa_onnx` Flutter package (Android, iOS, Windows, macOS, Linux)
- **LLM:** desktop → Ollama over localhost; phone → `flutter_edge_ai` (formerly flutter_gemma; LiteRT-LM or llama.cpp GGUF) with a 1–4B model
- **Storage:** SQLite (journal, events, state timeline) + `sqlite-vec` for semantic recall; raw EEG files separate; encrypt at rest

_Alternative if Dart DSP becomes a bottleneck:_ move BLE + DSP into a Rust core (muse-rs) via `flutter_rust_bridge`. Don't start there because it adds cross-compile complexity for every platform.

### Phase 2: Phone as hub + wearables
```
Muse S Athena ──BLE──► Phone (hub: DSP, classifier, small LLM, STT/TTS)
BLE HID ring/clicker ─► Phone ("mark this moment", push-to-talk)
Phone ──BT audio──► Bone-conduction glasses (cues, spoken reflections)
Phone ──LAN (opt.)─► PC/Ollama for heavier reflection & weekly summaries
```
Bone-conduction glasses are just Bluetooth audio, so no special SDK is needed. A HID ring turns "tag this moment" into a single tap. That tap is the most valuable label source you will have.

## 4. Realtime-conversation APIs vs. pipeline

**Use an offline pipeline: VAD → STT → LLM → TTS.** Realtime speech-to-speech APIs are cloud-only and would ship biometric context off-device. They also solve a problem you don't have: the brain loop doesn't need sub-second *conversation*.

**Two-speed architecture** (put this in the constitution):

| Loop | Latency | Driven by | Output |
|---|---|---|---|
| **Fast** | < 1 s | Deterministic classifier + rules (no LLM) | Tone / haptic / short bone-conduction cue |
| **Slow** | seconds–minutes | LLM over state *summaries* + your words | Probes, journal entries, reflections, weekly patterns |

The LLM never sees raw EEG. It sees things like `"14:02–14:09 focus high → 14:09 alpha rise + HR drop (p=0.71 mind-wandering) → probe answered: 'thinking about the call with my brother'"`.

## 5. Constitution seeds (for `/speckit.constitution`)

1. **Local-first:** raw biosignals never leave the device; cloud LLM is opt-in per request and receives summaries only.
2. **No mind-reading claims:** every state inference is shown as a hypothesis with confidence; the user's self-report always overrides the model.
3. **Not a medical device:** no diagnostic language.
4. **Signal integrity:** EEG 256 Hz, IMU 52 Hz, optics 64 Hz; filters and feature definitions are versioned; any change must be validated against stored reference recordings.
5. **Two-speed loop:** fast loop is deterministic and < 1 s; LLM is never in the fast path.
6. **Signal quality first:** no inference is emitted while electrode contact or motion artifacts exceed thresholds.
7. **Portable core contract:** feature definitions + ONNX model + recording format are the interface between Python research and the Flutter app.
8. **Connection UX:** auto-reconnect to last headband, per-electrode contact indicator, no manual pairing steps.

## Sources
- BrainFlow 5.22 Athena release: https://brainflow.org/2026-05-08-muse-anthena/
- BrainFlow supported boards: https://brainflow.readthedocs.io/en/stable/SupportedBoards.html
- OpenMuse: https://github.com/DominiqueMakowski/OpenMuse
- muse-rs: https://docs.rs/crate/muse-rs/latest
- sherpa_onnx (Flutter): https://pub.dev/packages/sherpa_onnx
- flutter_edge_ai / flutter_gemma: https://pub.dev/documentation/flutter_edge_ai/2.4.1/
- Mind-wandering EEG evidence: https://pmc.ncbi.nlm.nih.gov/articles/PMC6711882 ; https://bassconnections.duke.edu/sites/default/files/site-images/EfficacyOfConsumer-BasedEEGDevicesForConductingFutureResearch.pdf ; https://arxiv.org/html/2510.20958v2
