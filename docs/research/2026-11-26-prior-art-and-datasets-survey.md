# Prior art, open datasets and libraries, by roadmap feature (2026-11-26)

What already exists that MuFuse can use, test against or learn from, for every feature from 001
to 018. It adds to the three earlier research notes in this folder and does not repeat them.
Where it contradicts them, the correction is listed in [section 6](#6-proposed-corrections-to-existing-documents).
Only public sources are cited. Muse's SDK documentation is confidential under its licence and is
not quoted here.

Nothing in this note has been built. Every "adopt" is a recommendation for the feature's spec.

## How this was produced, and how far to trust it

- Eight research passes, one per area, each judged every candidate against the same constraints:
  Python 3.13 to 3.15 (CI runs 3.15), numpy 2.5, scipy 1.18, Ubuntu and Windows, pyright strict,
  MIT licence, local-first, **works on AF7 and AF8 alone**, four channels, not a medical device.
- 226 candidates came back. The 95 proposed as *adopt* or *evaluate* were then checked by a second,
  independent pass that tried to refute them: **83 confirmed, 12 corrected, 0 refuted.** For 5 more
  the facts held but the recommendation was lowered.
- **The 131 *learn-from* and *skip* items were not independently checked.** Treat their details
  (version numbers, licences, figures) as one reader's notes until someone re-reads the source.
- Two figures are a researcher's own estimate and come from no publication: the comparison of
  exponent spread between estimators in [3.3](#33-feature-003-eeg-features), and the label counts
  needed to detect a given AUC in [3.7](#37-feature-006-observations-and-interpreter-plug-ins).
- Package compatibility was checked by resolving and by reading wheel tags, mostly not by running
  the package. Where something was run on the project interpreter, the text says so.

Status column in the tables: **C** confirmed, **X** corrected (the correction is in the row),
**L** facts confirmed but recommendation lowered, **n** not independently checked.

## 1. What to do with this

The items below are the ones that change a spec. All are confirmed unless marked.

| Feature | Recommendation |
|---|---|
| 002 | Score the gate on two sets: a public Muse 2 artifact set (fetched, never committed) and our own Athena recordings. Use BrainFlow's new signal-quality call as a second opinion only. Nothing is ready to adopt as a dependency. |
| 003 EEG | Define the aperiodic exponent as a **censored regression** written in our own numpy code, not as "fooof". Keep fooof out of the runtime. Build on `scipy.signal` with carried filter state, freeze outputs with pytest-regressions, and give the simulator a 1/f background with bursts of alpha. |
| 003 PPG | Re-implement the MSPTDfast v2 beat detector in typed numpy. Measure pulse variability against an ECG reference before trusting it at 64 Hz. |
| 005 | Schedule prompts with exponential gaps (TagTime), use published thought-probe wording, register the marker hotkey with Windows `RegisterHotKey`, and store everything in stdlib SQLite. No new dependency is needed. |
| 006 | scikit-learn for a small within-person model. Judge it with a blocked permutation test on random-probe answers only. **The planned "retire after 40 labels" rule cannot work** (see 3.7). |
| 007 | sherpa-onnx **2.0 or later** (earlier versions embed GPL code), Ollama 0.31.2 or later with a JSON schema, a deterministic output filter built from the FDA general-wellness categories, and a test that fails if the voice path opens a non-loopback socket. |
| 008 | `scipy.stats.bootstrap` and `permutation_test`, resampling whole sessions or days. Show a number, a range and n. |
| 010 | Plan on `universal_ble`, not `flutter_blue_plus` (its licence is not open for commercial use). |
| All | Add a licence note about SimpleBLE inside BrainFlow (section 2.2). |

## 2. Findings that cut across features

### 2.1 Python 3.15 is the real filter

CI runs 3.15, and several well-known packages do not install there yet. `uv` ignores an upper
bound in `requires-python`, so a successful resolve is not evidence that a package supports 3.15.

| Blocked on 3.15 | Reason | Affects |
|---|---|---|
| onnxruntime 1.32.0 | no cp315 wheel and no source distribution | 006 ONNX export, 007 Smart Turn, 012 |
| h5py | no cp315 wheel; a build needs the HDF5 C library | any SNIRF or HDF5 export (004) |
| pandas 2.x | no cp315 wheel | pyrasa and anything pinned below pandas 3 |
| numba | caps numpy below 2.6 | antropy, stumpy, pyod |
| ruptures (< 3.14), tsbootstrap (< 3.15), physiokit (< 3.15), pocket-tts (< 3.15), kokoro-onnx (< 3.14), guardrails-ai and nemoguardrails (< 3.14), RealtimeSTT (< 3.13) | declared upper bound | 006, 007, 008, 009 |

Consequences:

- Heavy scientific libraries fit as **development-only oracles**: a test compares MuFuse's own
  typed function against the library on 3.13 or 3.14, and the runtime depends on numpy and scipy
  only.
- ONNX has to be an optional extra, tested on 3.13 and 3.14, until onnxruntime ships cp315 wheels.
- None of fooof, specparam, neurodsp, antropy, brainflow or sqlcipher3 ships `py.typed`. Each
  needs a thin typed wrapper to pass pyright strict.

### 2.2 Licences that need a decision

This is a reading of licence texts, not legal advice.

| Item | Finding | Status |
|---|---|---|
| SimpleBLE inside BrainFlow | BrainFlow is MIT, but it bundles SimpleBLE, which is under BUSL 1.1 with a grant specific to BrainFlow that forbids using or redistributing SimpleBLE outside BrainFlow. MuFuse's use through BrainFlow is inside that grant. Our licence notes should say so, and a repackaged or commercial distribution needs the owner to read the terms. The bundled version is 0.12.1; upstream is at 1.4.0. | X |
| [flutter_blue_plus](https://github.com/chipweinberger/flutter_blue_plus) | Its own licence (v1.6) is free for personal, nonprofit and educational use only. For-profit use, including evaluation, needs a paid licence. Relicensing is prohibited and the build pings a licence server. Drop it from the plan. | n |
| sherpa-onnx before 2.0 | Embedded espeak-ng, which is GPL. Version 2.0.0 (2026-10-23) removed it. Require 2.0 or later. | C |
| piper-tts | Now GPL-3.0-or-later. The MIT project (rhasspy/piper) is archived. Not an MIT option any more. | n |
| WildPPG | Data CC BY-NC-SA 4.0 and code GPL-3.0 according to the repository; the Hugging Face card says MIT. Treat it as non-commercial. Local validation only, never redistributed. | C |
| GPL packages to keep out | snirf / pysnirf2, PsychoPy, pingouin, mtspec, hrv-analysis, systole, vital-sqi, PyQt6, and `strict-rfc3339` (pulled in by ActivityWatch's aw-client). | n |
| No licence at all | OpenMuse has "MIT" in its package metadata but no LICENSE file. The UNIVERSE companion code, the authors' code for the censored-regression paper, eeg-artifact-scope, ErikBjare/thesis and antonio-pedro-ribeiro/muse have none. Read them; do not copy from them. | n |
| CC-BY models | Parakeet TDT is CC-BY-4.0. Shipping or downloading it needs an entry in a NOTICE file. | C |

### 2.3 MuFuse is no longer alone

Three projects overlap with MuFuse and are missing from our documents. None can be copied.
(Not independently checked.)

| Project | What it is | Licence |
|---|---|---|
| [NeuroSkill](https://github.com/NeuroSkill-com/skill) | Local-first EEG with a local LLM, Tauri and Rust, supports the Athena through muse-rs, v0.1.3 on 2026-11-20. Ships named stress, mood and migraine scores. Its `docs/HOOKS.md` and `docs/METRICS.md` are worth reading for design. | GPL-3.0 |
| [antonio-pedro-ribeiro/muse](https://github.com/antonio-pedro-ribeiro/muse) | "Muse Monitor": Python 3.13, uv, Typer and Rich, bleak, a FastAPI web view and a plug-in kernel, built on OpenMuse. Created 2026-11-06. | none |
| [bmp02050/tare](https://github.com/bmp02050/tare) | Check-in app in Kotlin with random prompts and a crisis plan the user writes. | PolyForm Noncommercial |

What still sets MuFuse apart: MIT licence; describing a signal change instead of naming a state;
a hit rate tested against random probes; the Athena's fNIRS; working on the forehead sensors
alone.

## 3. By feature

### 3.1 Feature 001: acquisition, recording, interoperability

| Rec. | Item | Status | Notes |
|---|---|---|---|
| evaluate | Retiming by regression on the sample counter ([liblsl](https://github.com/sccn/liblsl/blob/main/src/time_postprocessor.cpp) live, pyxdf offline) | C | About 50 lines of our own code would replace the body of `Retimer.retime`. liblsl smooths with a 90 s half-life; ours is about 100 samples. Reasoned from code, not measured: compare both on saved sessions first. Needs the per-sample counter passed in, and that counter is 8 bits and wraps. |
| evaluate | Requests to [BrainFlow](https://github.com/brainflow-dev/brainflow) | C | Upgrading gains nothing. Four things to send upstream: evidence that the battery scale reads half on 3.1.31, exposing stream 0x53, registering SimpleBLE's disconnect callback, updating the bundled SimpleBLE. Watch PR #885 (Polar H10) and issue #887 (an open recording format for consumer EEG, with null tests). |
| evaluate | [bleak](https://github.com/hbldh/bleak) 3.1.0, already a dependency | C | `BleakAdapter.get_connected_devices()` for `mufuse devices`. Windows rules from its issue tracker: do not pair the headband in Windows settings (#1949), wait before reconnecting (#2017), never hold a bleak connection while BrainFlow connects (#367), expect a stale GATT cache after a firmware update (#1940). |
| evaluate | [edfio](https://github.com/the-siesta-group/edfio) 0.4.18, Apache-2.0 | C | `mufuse export --format bdf`. 24-bit BDF holds the 20-bit optics. Gaps are padded and annotated, or the file is split. Pure Python; tracks numpy 2.5. |
| evaluate | [pylsl](https://github.com/labstreaminglayer/pylsl) 1.19.0 with pyxdf | C | `mufuse stream --lsl` as an optional extra. LSL uses UDP multicast, so bind to loopback or document it. |
| evaluate | [Ravi, Athena recordings with ECG reference](https://zenodo.org/records/23744414) (v2.1, CC BY 4.0, 38 MB) | C | **The one public Athena dataset.** EEG, PPG, 500 Hz ECG, documented dropouts and poor contact. Needs a small importer to the playback format, and its optics order must be confirmed. Useful for 001, 002 and 003. |

Read, do not depend on (not checked): [muse.js](https://github.com/Polobase/muse.js) protocol notes
(no 256 kHz device clock; the 0x88 battery subpacket is a fixed 20 bytes, and misreading it
inflated loss to 2.3%; the packet counter is 16 bits); [muse-rs](https://github.com/eugenehp/muse-rs);
[muse-lsl](https://github.com/alexandrebarachant/muse-lsl) 2.5.3 (uses battery / 512).

Rejected: SimpleBLE or simplepyble directly (licence, 2.2); pyedflib; Parquet or Zarr as an export
format; PsychoPy (GPL); Timeflux, goofi-pipe and MNE-LSL; OpenMuse (no LICENSE file);
urish/muse-js.

Open questions:

- What is MuFuse's own lost-subpacket rate on 3.1.31?
- Does the battery scale differ by firmware?
- Is the regression retimer measurably better on our recordings?
- In BDF, are gaps padded or does the file split?

### 3.2 Feature 002: signal quality

Nothing here is ready to adopt. The gate needs data before it needs a library.

| Rec. | Item | Status | Notes |
|---|---|---|---|
| evaluate | [Lee and Ahn, consumer- and research-grade EEG](https://doi.org/10.6084/m9.figshare.30162868.v1) (CC BY 4.0, 1.08 GB) | L | 30 people on a Muse 2 (same four sites, 256 Hz) doing cued blinks, jaw clenches and head turns, 20 of each. The paper reports 20 of 20 blinks and 19.85 of 20 clenches detected. Lowered from adopt: noisy recordings were left out of the release, the labels are cue beeps every 3 s and not the movement itself, the paper analysed AF7 re-referenced to TP10, and it is a Muse 2. Use a fetch script; do not vendor it. |
| evaluate | BrainFlow 5.24.0 [`DataFilter.get_signal_quality`](https://github.com/brainflow-dev/brainflow/pull/875) | C | Flags non-finite, clipped and flat channels. Already installed. A second opinion for `signal_check.py`: it is stateless, does not detect mains hum from a lifted sensor, and returns plain dicts. Its pull request reports TP10 rejected for clipping in 103 of 322 six-second windows on a worn Athena, which is outside evidence for issue #12. |
| evaluate | Stream 0x53 (DRL/REF) as a worn / not worn signal | X | BrainFlow reads the tag and skips it. muse.js measured a spread of 145 to 221 counts on a desk against 3 to 17 worn, on one unit. Correction: the BrainFlow maintainer has already said in issue #835 that not parsing everything is intended, so a pull request may not be welcome. Keep it behind a hardware check. |
| evaluate | [pyRiemann](https://github.com/pyRiemann/pyRiemann) Potato | C | Works on two channels online, but pulls scikit-learn, joblib and matplotlib. A 2 x 2 version is a few lines of scipy. On AF7 and AF8 a covariance matrix has three free values per band, so it adds little over band power and coherence. |
| evaluate | [OpenNeuro ds009136](https://openneuro.org/datasets/ds009136/versions/1.0.0) (CC0, 2.88 GB) | X | Dry headset with head IMU during nods, shakes and walking: for the motion gate. No AF7 or AF8. Correction: two subjects used a 32-channel headset. |
| evaluate | [Zenodo 8429740](https://doi.org/10.5281/zenodo.8429740) (CC BY 4.0, 315 MB) | C | Muse S with accelerometer, gyroscope and Muse's own blink and jaw flags. Those flags are a detector's output, not ground truth. |
| evaluate | [Kaggle Muse 2 facial movements](https://www.kaggle.com/datasets/dangnguyenyuu/muse-2-eeg-facial-movements-dataset) | C | Three people. The companion code has no licence. |

Read, do not depend on (not checked):

- A blink recipe from eeg-artifact-scope: band 1 to 10 Hz, Hilbert envelope, 0.5 s smoothing,
  robust z above 4, 0.8 s refractory, width under 1.2 s.
- MNE's `annotate_muscle_zscore`: its default band of 110 to 140 Hz does not fit under our 128 Hz
  Nyquist. A muscle band for the Athena must also avoid mains and the device lines at 21.3, 42.7
  and 64 Hz.
- Two open thresholds to compare ours with: muse.js (spread 150 / 400 µV over 5 s; 2% / 10% of
  samples at the rail) and [Grosselin 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6387437)
  (1 s windows; more than 70% constant values or beyond 300 µV is low quality). **MuFuse's 75 µV
  limit is stricter than both.**
- Ear-contact advice, read through search snippets only because the forum blocks fetching: more
  pressure over the ear pads (pull the back of the band down, or wear a beanie over it), several
  minutes of settling, a thin smear of electrode gel, reseating the pod and checking the contacts
  between pod and band.

Rejected: Artifact Subspace Reconstruction (asrpy, meegkit), autoreject and pyprep (all assume
many channels); the TUH artifact corpus (clinical montage, access by application); the Georgia
Tech blink sets (no licence).

Open questions:

- Is the gate scored on the public Muse 2 set, on our own Athena recordings, or both?
- How is "head turn detected" defined on the Muse 2 set, which has no accelerometer data?
- Does 0x53 separate worn from not worn on firmware 3.1.31?
- When TP10 drops, is it railed or humming?

### 3.3 Feature 003: EEG features

| Rec. | Item | Status | Notes |
|---|---|---|---|
| adopt | Censored-regression aperiodic exponent ([Kałamała et al. 2026](https://pmc.ncbi.nlm.nih.gov/articles/PMC13000880/)) | C | Leave the alpha band out and fit a line to log power against log frequency. About ten lines of numpy, deterministic, and easy to port to Dart for feature 011. The paper reports reliability above 0.9 from about 30 to 40 one-second epochs. It gives no periodic estimate, so the alpha peak needs its own step with "no peak found" as a normal result. The authors' code has no licence: write our own. |
| adopt | [`scipy.signal`](https://docs.scipy.org/doc/scipy/reference/signal.html): `sosfilt` with carried state, `welch`, `ShortTimeFFT`, `windows.dpss` | C | Filtering in chunks with carried state was bit-identical to filtering in one call (run here). Reset the state after a gap above 0.25 s and discard a settling period. Golden files must say whether a filter is causal or zero-phase. |
| adopt | [pytest-regressions](https://pypi.org/project/pytest-regressions/) 2.11.0, MIT, typed | C | Use `ndarrays_regression` only, set `atol` and `rtol` explicitly, and build golden files from the simulator only. |
| adopt | A 1/f background with bursts of alpha in `simulated.py` | C | Today's simulated EEG is a 10 Hz sine on white noise, identical on every channel, so no spectral feature can be tested on it. Add it as a new named profile so the 001 rehearsal does not change. |
| evaluate | [fooof](https://pypi.org/project/fooof/) 1.1.1, Apache-2.0 | X | Proposed as a development-only oracle; lowered. It is deprecated, it calls `warnings.simplefilter('always')` at import, and its own CI stops at Python 3.11. If used: pin `==1.1.1`, import it lazily inside `warnings.catch_warnings()`, and keep it in tests. |
| evaluate | [specparam](https://pypi.org/project/specparam/) 2.0.0rc7 | C | Still a release candidate. Not numerically identical to fooof (exponent 1.4447 against 1.4540 on the same input). |
| evaluate | BrainFlow 5.24.0 `StreamingFilter`, `BandPowerContext` | C | Second opinion only. |
| evaluate | [antropy](https://pypi.org/project/antropy/) 0.2.3 | C | Through numba it caps numpy below 2.6. |
| evaluate | [HEROIC Muse 2 resting data](https://zenodo.org/records/11493897) (CC BY 4.0, 86 MB) | C | Real resting spectra at our four sites. The software beside it is GPL; take the data only. |
| learn-from | [pyrasa](https://pypi.org/project/pyrasa/) 1.1.1 | X | Does not install on 3.15 (pins pandas below 3). |

A researcher's simulation, not a published result: the spread of the exponent over repeated draws
was 0.15 / 0.08 / 0.045 for windows of 4 / 10 / 30 s with censored regression, against
0.22 / 0.11 / 0.054 for fooof in its best case.

Read, do not depend on (not checked):

- [Gerster 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9588478/): fit the spectrum of minimally
  filtered data, and keep the high-pass stopband and the 60 Hz notch outside the fit range.
- [Hashemi 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC5150228/): in Muse recordings an alpha
  peak showed at AF7 or AF8 in about half of eyes-closed sessions. A missing frontal peak is normal.
- [Buchheit 2014](https://pmc.ncbi.nlm.nih.gov/articles/PMC3936188/): a rolling median with a
  scaled MAD as the personal baseline. `signal_check.spread_uv` already computes 1.4826 x MAD.
- The BLINK algorithm (Agarwal and Sivakumar 2019): re-implement from the paper.

Rejected: syrupy, yasa, mne-features, meegkit, pyeeg, ruptures, mtspec (GPL), `mne.simulation`.

Open questions:

- Where does the Athena's noise floor begin at AF7 and AF8, and so where must the fit range end?
- Is a frontal alpha peak detectable for this user at all?
- What is the shortest window that gives a stable exponent?
- What tolerance do the golden files allow across platforms and Python versions?

### 3.4 Feature 003 (pulse) and 009 (breathing)

MuFuse today has only a spectral pulse check (`optics.py`, `pulse_share`).

| Rec. | Item | Status | Notes |
|---|---|---|---|
| adopt | MSPTDfast v2 beat detection ([Charlton 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC11894679/); NeuroKit2 has an MIT port) | C | Re-implement in typed numpy and scipy, about 100 lines, on rolling windows of 6 to 8 s, with golden outputs compared against the NeuroKit2 port. It has no validation on the forehead or on the Athena. |
| evaluate | Sub-sample peak refinement before RMSSD ([Béres 2019](https://www.measurement.sk/2019/msr-2019-0030.pdf)) | X | At 64 Hz, rounding beat times to a sample adds about 11 ms RMS to successive differences, so a true RMSSD of 20 ms reads about 23 ms. Lowered from adopt: the paper is a simulation and interpolation did worse in one series. Measure the gain against ECG first. |
| evaluate | [PPG-DaLiA](https://archive.ics.uci.edu/dataset/495/ppg+dalia) (CC BY 4.0, about 2.7 GB) | L | Wrist PPG at 64 Hz with chest ECG. An offline benchmark only: wrist, not forehead. |
| evaluate | [NeuroKit2](https://github.com/neuropsychology/NeuroKit) 0.3.0, MIT | C | Development and test oracle only: heavy dependencies and untyped. |
| evaluate | [WildPPG](https://siplab.org/projects/WildPPG) | C | The only open set with forehead PPG and ECG. Non-commercial (2.2). |
| evaluate | [BIDMC PPG and Respiration](https://physionet.org/content/bidmc/1.0.0/) (ODC-By) | C | For breathing rate from the pulse wave. |
| evaluate | A chest strap over the standard BLE Heart Rate Service ([bleakheart](https://github.com/fsmeraldi/bleakheart), MPL-2.0) | C | The reference the 003 gate asks for. Two BLE links on one adapter need a hardware check. |
| evaluate | Breathing rate from pulse modulations (amplitude, baseline, beat interval) | X | Correction: the RRest toolbox is GPL and physiokit does not support 3.15, so read physiokit's BSD-3 code and re-implement. At 64 Hz the beat-interval method will be the weakest. |
| evaluate | [Pulse Transit Time PPG](https://physionet.org/content/pulse-transit-time-ppg/1.1.0/) (ODbL) | C | A further benchmark with ECG. |

Read, do not depend on (not checked): [OpenHRV](https://github.com/JanCBrammer/OpenHRV) (LGPL-2.1)
paces breathing with `0.5 + 0.5*sin(2*pi*rate/60*t)` and feeds back the peak-to-trough swing of
the beat interval, which is typically 100 ms or more at 6 breaths a minute and so far above the
11 ms timing noise. A study of the Muse 2 forehead PPG against a Polar H10
([Griadhi 2026](https://zenodo.org/records/23091944)) found heart rate agreed and ultra-short
RMSSD was overestimated.

Rejected: heartpy, pyPPG, BioSPPy, pyHRV (unmaintained or incompatible); hrv-analysis, systole,
vital-sqi (GPL); WESAD (non-commercial); SpO2 by ratio of ratios (medical claim, uncalibrated).

Open questions:

- Does the user own a BLE chest strap?
- What exactly does "within ±3 bpm" mean: per window, per session, mean or 95% limits?
- Should the 009 gate use RMSSD, or the peak-to-trough swing, which 64 Hz measures far better?
- Which optics rows give the best pulse?

### 3.5 Feature 004: fNIRS

| Rec. | Item | Status | Notes |
|---|---|---|---|
| evaluate | [OpenNeuro ds007554](https://openneuro.org/datasets/ds007554) (CC0) | C | Prefrontal fNIRS raw intensity with n-back and arithmetic: a rehearsal for the pipeline before our own validation sessions. |
| learn-from | MNE-NIRS `write_raw_snirf` | X | Lowered from evaluate: h5py has no cp315 wheel, so every HDF5-based SNIRF path is blocked on 3.15. The writer also expects two wavelengths per channel, and the Athena's source-detector distance is still unmeasured. |

Not checked: [OpenMuse PR #31](https://github.com/DominiqueMakowski/OpenMuse/pull/31) is still open
and carries an independent cross-check that supports the wire order MuFuse uses. Cedalion 25.1.0
pins numpy 2.2 and cannot be installed beside MuFuse. muse.js notes that optical counts cannot be
calibrated to a physical unit.

Rejected: snirf / pysnirf2 (GPL); Tufts fNIRS2MW (access by application).

Open question: the source-detector distance, which feature 004 already lists as a prerequisite.

### 3.6 Feature 005: labelling loop

No new dependency is needed for the first version.

| Rec. | Item | Status | Notes |
|---|---|---|---|
| adopt | Exponential gaps between prompts ([TagTime](https://github.com/tagtime/TagTime), the idea only) | C | The next prompt cannot be anticipated. Seed the generator so it works with `FakeClock`. A minimum gap and quiet hours truncate the distribution; record that they do. |
| adopt | Probe wording from [Kane et al. 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC8613094/) and Robison, Miller and Unsworth 2019 | C | Ask about content. Never fewer than three options. Keep mind-wandering, outside distraction and mind-blanking apart. Eight options are too many for one tap, so the short set needs a pilot. |
| adopt | Windows [`RegisterHotKey`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey) through ctypes | C | A global marker key with no dependency: a small message-loop thread puts a marker on a queue. It is a new component, since `keys.py` only reads terminal keys. Windows only; the key must be configurable and a failed registration reported. |
| adopt | stdlib [`sqlite3`](https://docs.python.org/3/library/sqlite3.html): WAL, STRICT tables, FTS5, JSON functions | C | Checked on the project interpreter (SQLite 3.53.1); not run on Ubuntu. One append-only events table with `source` as a checked NOT NULL column, so random-probe and self-started labels can never be pooled. Check the capabilities at start-up. |
| evaluate | [ActivityWatch](https://github.com/ActivityWatch/activitywatch) (MPL-2.0) as an optional context source | X | Lowered from adopt. Its Python client cannot be a dependency (it pins platformdirs 3.10 and pulls a GPL package), so read its REST API on 127.0.0.1:5600 with the stdlib. The Rust server can require an API key. It is a separate app the user must run. Window titles are the most sensitive data MuFuse would touch: store a derived category. Its away-from-keyboard record lets the scheduler skip prompts and mark one as "not seen". |
| evaluate | [desktop-notifier](https://pypi.org/project/desktop-notifier/) 6.2.0, MIT | C | The cheapest way to try the prompt loop. Windows Focus Assist hides notifications, so log those as "not seen". Not proven at runtime on 3.15. |
| evaluate | [pywebview](https://pypi.org/project/pywebview/) 6.2.1, BSD-3 | C | A frameless always-on-top strip that opens into an HTML chat. No transparency on Windows. Depends on pythonnet and WebView2; one dependency is source-only. |
| evaluate | tkinter (stdlib) | C | A throwaway strip with no dependency. |
| evaluate | [PySide6](https://pypi.org/project/PySide6/) 6.12.0, LGPL | C | Large. PyQt6 is GPL and must be avoided. |
| evaluate | [pynput](https://pypi.org/project/pynput/) 1.8.2, LGPL-3.0 | C | Optional extra for a hotkey on macOS and X11. No Wayland. |
| evaluate | [DuckDB](https://duckdb.org/) 2.0.1, MIT | C | `ASOF JOIN` aligns labels with features. Its SQLite extension is downloaded on first use, which is a network call. `numpy.searchsorted` may be enough. |
| evaluate | [sqlcipher3](https://pypi.org/project/sqlcipher3/) 0.6.5 | X | Correction: wheels cover Linux and Windows up to cp315, so one package serves both CI platforms. It encrypts the database only, not the `.f64` recordings, and key management is unsolved. |
| evaluate | [apsw-sqlite3mc](https://pypi.org/project/apsw-sqlite3mc/) | X | Correction: released 2026-11-16 with cp315 wheels. Not DB-API compatible. |
| evaluate | [icalendar](https://pypi.org/project/icalendar/) 7.3.2 with recurring-ical-events (LGPL) | C | Calendar context from `.ics` files, for 008 and 017. |
| evaluate | [jsPsych](https://github.com/jspsych/jsPsych) 8.4.0, MIT | C | Browser tasks that post markers to a loopback-only endpoint. Relevant to 016. |
| skip | [sqlite-vec](https://github.com/asg017/sqlite-vec) | L | Lowered from evaluate: pre-1.0 with breaking changes announced, and no stable release since 2026-03-31. A numpy cosine search is enough at journal size. |

Read, do not depend on (not checked):

- The TIME study ([Ponnada 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC8867293/)): 662,397
  one-tap prompts, about four an hour, 67.6% answered, with a minimum gap of 8 minutes.
- [Eisele 2022](https://doi.org/10.1177/1073191120957102): the length of the questionnaire, not
  how often it comes, is what raises burden.
- A BLE ring pairs as an ordinary keyboard. Read it through the OS (Raw Input), not through bleak,
  which blocks the HID service on Windows ([bleak PR #655](https://github.com/hbldh/bleak/pull/655)).

Rejected: the open experience-sampling platforms (server-based, or AGPL); the `keyboard` package;
Wayland portal bindings; pystray and the toast libraries.

Open questions:

- Will the user run ActivityWatch, and is a category enough?
- Which ring, and which key does it send?
- What should encryption at rest cover, and is BitLocker enough?
- How is a prompt that was never seen recorded and counted in compliance?
- What is the short one-tap category set?

### 3.7 Feature 006: observations and interpreter plug-ins

Three findings change the design before any library does.

1. **No open dataset pairs a Muse-class headband with thought-probe labels.** MuFuse's own random
   probes will be the only direct evidence.
2. **Models across people barely beat chance.** A 2026 benchmark found AUC 0.51 to 0.63 on six of
   seven EEG datasets ([Bodonhelyi 2026](https://arxiv.org/abs/2604.09569)). Tang 2025 found 0.68
   within a person against 0.56 across people. Only within-person models are worth building.
3. **The group-level evidence for AF7 and AF8 is negative.** In
   [Ronca 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12779824/) the Muse S indices did not
   separate easy from hard tasks, and needed 10 to 15 s of smoothing. Observation windows should
   be at least that long, and band-ratio "attention indices" are unproven.

(All three are from the not-checked group.)

| Rec. | Item | Status | Notes |
|---|---|---|---|
| adopt | [scikit-learn](https://pypi.org/project/scikit-learn/) 1.9.1, BSD-3 | C | Has cp315 wheels on both platforms. A scaler and a logistic regression on a few forehead and blink features, cross-validated by day. Partial type stubs: wrap it, and keep it out of the acquisition path. |
| adopt | A blocked permutation test and a Beta-Binomial posterior, from scipy and scikit-learn | C | AUC of frozen scores against random-probe answers only, shuffled within a day. Fix the look schedule in the manifest (for example after 50, 100 and 150 labels), or repeated looks will find an effect by chance. |
| evaluate | [UNIVERSE](https://zenodo.org/records/10371068) (CC BY 4.0, 20.3 GB) | C | 24 people, about 315 hours, Muse S and a wrist band, lab and home office. Its own validation reached 71% and 74%, with the worst individuals at 48% and 54%. Workload labels, not thought probes. Its companion code has no licence. |
| evaluate | [OpenNeuro ds001787](https://openneuro.org/datasets/ds001787) (CC0, 6.11 GB) | C | Meditation with experience-sampling probes, 24 people. The smallest clean probe dataset: a first rehearsal for probe-locked windows. |
| evaluate | [ATTLAPSE](https://doi.org/10.5281/zenodo.23592484) (CC BY 4.0, 38 GB) | C | 56 people, sustained attention with probes, 64 channels, only 15 probes each. |
| evaluate | [river](https://pypi.org/project/river/) 0.27.0, BSD-3 | C | Its delayed-label progressive validation is shadow mode exactly. The pattern can also be copied in about 50 lines. |
| evaluate | skl2onnx 1.20.0 with onnxruntime 1.32.0 | C | Blocked on 3.15 (2.1). An optional extra at most. |
| evaluate | MAPIE 1.6.0, venn-abers 1.5.4 | C | Conformal prediction lets an interpreter abstain. Not needed before there are labels. |
| evaluate | [pluggy](https://pypi.org/project/pluggy/) 1.7.0, or a `typing.Protocol` with a first-party registry | C | Start with the Protocol. Keep an explicit allow-list if third-party plug-ins are ever loaded. |
| evaluate | Manifest parsing: PyYAML `safe_load` with msgspec or pydantic, or stdlib `tomllib` | C | All have cp315 wheels. YAML or TOML is a spec decision. |
| learn-from | [ROAMM](https://openneuro.org/datasets/ds007629) (CC0) | L | Lowered from evaluate: the BIDS part holds one participant. The rest is distributed as serialised Python objects (`.pkl`), a format that can run code when loaded, so those files are untrusted input and belong only in an isolated environment. |

The planned retirement rule is too weak. A researcher's approximation, from no source: with 40
labels the standard error of an AUC is near 0.09, so "retire if AUC ≤ 0.55 after 40 labels" cannot
tell 0.55 from 0.50 or from 0.70. Detecting an AUC of 0.65 takes about 90 to 100 balanced labels.
At six probes a day and 70% answered, two weeks gives about 60.

Design rules from the reading (not checked):

- Classifiers trained on vigilance or task demand do not predict mind wandering
  ([Jin, Borst, van Vugt 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7689771/)). Train only on
  probe labels.
- Every interpreter should beat a clock-only baseline and a blink-and-motion-only baseline, not
  only chance.
- Label the 10 s before a probe (Dhindsa 2019), and store a confidence rating with each answer
  (Tang 2025).

Rejected: EEG foundation models (0.45 to 0.51 balanced accuracy on a three-class Muse task, and
licence problems with several sets of weights); ruptures; stumpy and pyod; small Muse sets from
Kaggle and Zenodo; several sequential-testing packages.

Open questions:

- Is a blink-and-motion model acceptable as the first interpreter if it is labelled as such?
- How many probe labels are realistic in two weeks? Extend the Phase 0 exit window, or raise the
  probe rate?
- Does 005 store a confidence rating?
- Are third-party plug-ins in scope?

### 3.8 Feature 007: voice and local LLM

| Rec. | Item | Status | Notes |
|---|---|---|---|
| adopt | [sherpa-onnx](https://pypi.org/project/sherpa-onnx/) 2.0 or later, Apache-2.0, with Silero VAD | C | cp313 to cp315 wheels on both platforms; it bundles its own ONNX Runtime, so the block in 2.1 does not apply. The same version is on pub.dev for feature 013. Version 2.0.0 changed TTS: the built-in lexicon skips words it does not know. Vendor models with checksums. |
| adopt | [Ollama](https://github.com/ollama/ollama) 0.31.2 or later over HTTP with a `format` JSON schema | C | Set `OLLAMA_NO_CLOUD=1` (it ships cloud models and web search), set `num_ctx` explicitly, temperature 0, and validate the reply. Add a contract test that the schema is enforced: before 0.31.2 it was silently ignored for one model family. The desktop app updates itself. |
| adopt | A pydantic schema with validation, and no structured-output library | C | Keep the schema flat. On a validation failure speak a pre-written template; do not retry in a loop. |
| adopt | A deterministic output filter built from the [FDA general-wellness guidance](https://www.fda.gov/media/90652/download) (revised 2026-01-06) | C | Blocked: disease or condition names, diagnostic thresholds, "abnormal", prompts to seek or change treatment, accuracy claims, and "you are / you have / you seem" followed by a state or trait. Allowed: values, ranges, trends, baselines. Guidance only, United States only. |
| adopt | An egress checklist | C | `HF_HUB_OFFLINE=1` and `HF_HUB_DISABLE_TELEMETRY=1` before any import, `OLLAMA_NO_CLOUD=1`, models with checksums, and a CI test that fails if the voice or LLM path opens a non-loopback socket. |
| evaluate | Speech-to-text models through sherpa-onnx: [Parakeet TDT 0.6b](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) (CC-BY-4.0), Whisper turbo (MIT) as the baseline, [Moonshine v2](https://github.com/moonshine-ai/moonshine) | C | Choose by measured latency on the user's machine. |
| evaluate | Text-to-speech: [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) v1.0 (Apache-2.0), Pocket TTS, KittenTTS, all through sherpa-onnx | C | Pre-render the cue and crisis audio so those never depend on a model. |
| evaluate | [Smart Turn v3](https://github.com/pipecat-ai/smart-turn), BSD-2 | C | Detects the end of a turn. Needs onnxruntime, so not on 3.15 unless sherpa's bundled runtime can load it. |
| evaluate | Models for a bake-off: [Gemma 4 12B](https://huggingface.co/google/gemma-4-12B-it) (and E4B for the phone), Qwen3.5-9B, Granite 4.1 8B, phi-4 14B, Mistral Nemo 12B | C | None is chosen. |
| evaluate | [llama.cpp](https://github.com/ggml-org/llama.cpp) `llama-server`, MIT | C | A fallback runtime. Its schema converter skips unsupported features silently. |
| evaluate | Guard models: Granite Guardian 4.1 8B, Qwen3Guard 0.6B | C | An optional second line, never the only gate. |
| evaluate | [Suicide Risk Lexicon](https://github.com/danielmlow/construct-tracker) v1.0, vendored as data | C | Repository is Apache-2.0 but the data file states no licence of its own: ask the author. Validated on typed crisis-line text, not on speech. Do not install the package. |
| evaluate | [python-statemachine](https://pypi.org/project/python-statemachine/) 3.2.2, or about 100 lines of our own | C | For the crisis path and the cue ladder. |
| learn-from | [Hotline_Helper](https://github.com/agus-pleso/Hotline_Helper) (crisis lines by country) | X | Lowered from evaluate: its monthly update failed on all six runs, 201 of 249 country files are empty, and it has not changed since 2026-05-08. Copy the schema (source, last verified, status) and verify by hand any number MuFuse ships. |

Read, do not depend on (not checked):

- The [EU AI Act](https://artificialintelligenceact.eu/article/5/) treats inferring emotions from
  biometric data as high-risk and bans it at work and in education; physical states such as
  fatigue are excluded. This supports describing signals instead of naming states.
- Small models are poor crisis detectors and tend to agree with the user
  ([K-Bench](https://arxiv.org/abs/2609.15855)); general guardrails had sensitivity below 0.10 on
  some crisis categories ([Verily study](https://arxiv.org/abs/2510.12083)). Never use the LLM as
  the risk detector.
- [SSAG](https://arxiv.org/abs/2411.06723): scripted states with the LLM filling the wording,
  which is the plan for 018.
- [Pipecat](https://github.com/pipecat-ai/pipecat) for barge-in and turn-taking; the Wyoming
  protocol and hassil for typed voice events and fixed phrases such as "stop" and "snooze".

No openly licensed defusion or urge-surfing script was found. The 009 scripts must be written
originally.

Rejected: piper-tts (GPL); guardrails-ai and NeMo Guardrails (telemetry on by default, and capped
below 3.14); livekit-agents, RealtimeSTT, vocode, llm-guard, faster-whisper; models under custom
licences (Llama Guard, ShieldGemma, SenseVoice and others); suicide classifiers trained on Reddit.

Open questions:

- Which speech models meet the 1 s cue budget on the user's machine?
- Is the crisis script for the United States only (988), or for a configured country?
- Which lexicon constructs trigger the crisis script, and which a softer check-in?
- Does any free text reach the speaker, or only slot-filled templates?

### 3.9 Feature 008: journal and timeline

| Rec. | Item | Status | Notes |
|---|---|---|---|
| adopt | [`scipy.stats.bootstrap`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html) and `permutation_test` | C | Paired BCa intervals. Resample whole sessions or days: windows inside a session are correlated and would make every pattern look certain. Refuse to show a pattern below a minimum n. |
| adopt | Wording from [van der Bles et al. 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7149229/) | C | A number with a numeric range and n costs almost no trust. Vague verbal hedges do. |

Read, do not depend on (not checked): DABEST's estimation plots for style (the package pins numpy
2.1); [Perfice](https://github.com/p0lloc/perfice), which shows correlations with no n and no
effect size, the pattern feature 008 forbids; Apple's Vitals design (wait for a baseline, require
more than one signal, offer mundane explanations).

Rejected: pingouin (GPL); tsbootstrap and arch.

Open question: what is the unit of n, a session or a day?

### 3.10 Phase 1: the Flutter app (010 to 014)

| Rec. | Item | Status | Notes |
|---|---|---|---|
| adopt | [sherpa_onnx](https://pub.dev/packages/sherpa_onnx) for Flutter 2.0.3, Apache-2.0 | C | Same engine and version as the Python side. |
| evaluate | [universal_ble](https://pub.dev/packages/universal_ble) 3.4.1, BSD-3 | C | All six platforms. Untested at the Athena's notification rate: a one-day spike that counts the 16-bit packet counter would answer it. |
| evaluate | [Elata SDK](https://github.com/Elata-Biosciences/elata-bio-sdk), MIT | C | A Rust Athena decoder with WASM and mobile bindings, and a script that compares its decode with another. A second reference for the Dart decoder. Check that nothing phones home. |
| evaluate | BrainFlow's Android AAR | X | Correction: it packages SimpleBLE under the terms in 2.2. Board 67 on Android is undocumented, there is no iOS path, and the file is about 100 MB. |
| evaluate | [flutter_onnxruntime](https://pub.dev/packages/flutter_onnxruntime) 1.9.1, MIT | C | The older `onnxruntime` package has had no release since 2024-03. |
| evaluate | [flutter_edge_ai](https://github.com/DenisovAV/flutter_edge_ai) 2.7.2 and llamadart 0.22.0 | C | Needs Flutter 3.44 and Dart 3.12. flutter_gemma is discontinued. |
| evaluate | Dart DSP: [fftea](https://pub.dev/packages/fftea), scidart | C | No maintained Dart IIR filter package exists: export the SOS coefficients from SciPy and write the loop. No Dart fooof exists, which is one more reason for the censored regression in 3.3. |
| evaluate | `mufuse serve`: [websockets](https://pypi.org/project/websockets/) 17.4, or Starlette with uvicorn | C | websockets has no dependencies. FastAPI brings pydantic and, since 0.165, an OpenTelemetry package. Bind 127.0.0.1 and use a per-run token. |
| evaluate | [NiceGUI](https://pypi.org/project/nicegui/) 4.1.0, MIT | C | Fast to build, but it merges server and view, against the `mufuse serve` boundary. |
| learn-from | [muse.js](https://github.com/Polobase/muse.js) | L | Lowered from evaluate: unpublished and quiet for two months. Its value is the measured protocol notes. |

Athena facts from public threads, for the Dart decoder (not checked):

- Presets with eight channels add four auxiliary inputs that carry no scalp signal.
- The 0x88 battery subpacket is a fixed 20 bytes.
- Firmware 3.1.29 sends notifications of at most 116 bytes more often, where 3.1.19 sent up to
  244 bytes. A golden decode fixture from one firmware does not cover the other.
- On one unit with firmware 3.1.23 a characteristic exposed Indicate instead of Notify (BrainFlow
  issue #835).

Also not checked: [neurofeed](https://github.com/windwerfer/neurofeed) shipped Flutter with a Rust
core and is now porting to pure Rust because the mix slowed development, which is evidence against
starting MuFuse's app with a Rust core.

Rejected: flutter_blue_plus (2.2); flutter_reactive_ble (phones only); pytauri, Electron, Flet;
berndie/flutter-muse (needs the Muse SDK); Fusion (the repository is gone).

Open questions:

- Is 010 pure Dart, or a wrapped decoder?
- Can universal_ble deliver the Athena stream without loss on Windows and Android?
- Does the golden decode fixture cover more than one firmware?
- Will MuFuse ever be distributed for profit? Several licence answers depend on it.

### 3.11 Phase 2 (015 to 018)

Nothing here is ready to choose. For the record: 016 can reuse the permutation test and look
schedule from 3.7, and jsPsych for timed tasks. [StudyU](https://github.com/studyu-health/studyu)
is an MIT n-of-1 platform in Flutter but appears to need a cloud back end (not checked). 018
follows the scripted-state pattern in 3.8.

## 4. Datasets in one place

None of these goes into the repository. Each needs a fetch script that checks a checksum, and the
licence and citation recorded beside it.

| Dataset | For | Device | Licence | Size |
|---|---|---|---|---|
| [Ravi, Athena with ECG](https://zenodo.org/records/23744414) | 001, 002, 003 | Muse S Athena | CC BY 4.0 | 38 MB |
| [Lee and Ahn](https://doi.org/10.6084/m9.figshare.30162868.v1) | 002 | Muse 2 | CC BY 4.0 | 1.08 GB |
| [Zenodo 8429740](https://doi.org/10.5281/zenodo.8429740) | 002 | Muse S | CC BY 4.0 | 315 MB |
| [ds009136](https://openneuro.org/datasets/ds009136/versions/1.0.0) | 002 motion | dry EEG with IMU | CC0 | 2.88 GB |
| [HEROIC](https://zenodo.org/records/11493897) | 003 EEG | Muse 2 | CC BY 4.0 | 86 MB |
| [PPG-DaLiA](https://archive.ics.uci.edu/dataset/495/ppg+dalia) | 003 pulse | wrist PPG with ECG | CC BY 4.0 | about 2.7 GB |
| [WildPPG](https://siplab.org/projects/WildPPG) | 003 pulse | forehead PPG with ECG | non-commercial | |
| [BIDMC](https://physionet.org/content/bidmc/1.0.0/) | 009 | clinical PPG with breathing | ODC-By | |
| [ds007554](https://openneuro.org/datasets/ds007554) | 004 | prefrontal fNIRS | CC0 | |
| [ds001787](https://openneuro.org/datasets/ds001787) | 006 | 64-channel EEG with probes | CC0 | 6.11 GB |
| [UNIVERSE](https://zenodo.org/records/10371068) | 006, 016 | Muse S with wrist band | CC BY 4.0 | 20.3 GB |
| [ATTLAPSE](https://doi.org/10.5281/zenodo.23592484) | 006 | 64-channel EEG with probes | CC BY 4.0 | 38 GB |

Start with the first one. It is the only recording from our own device, it is small, and it has
the ECG reference that the pulse gate needs.

## 5. Items the second pass changed

Corrected (the facts were wrong or incomplete):

1. Stream 0x53: the BrainFlow maintainer has already declined to parse everything (issue #835).
2. ds009136: two subjects used a different, 32-channel headset.
3. fooof: adopt to evaluate. Deprecated, and it changes the warning filter at import.
4. pyrasa: evaluate to learn-from. Does not install on 3.15.
5. Sub-sample peak refinement: adopt to evaluate. Simulation only, with one series made worse.
6. Breathing from PPG: RRest is GPL, and physiokit does not support 3.15.
7. MNE-NIRS SNIRF writer: evaluate to learn-from. h5py has no cp315 wheel.
8. ActivityWatch: adopt to evaluate. The client is unusable as a dependency.
9. sqlcipher3: wheel coverage is wider than first stated.
10. apsw-sqlite3mc: release date and wheel coverage.
11. Hotline_Helper: evaluate to learn-from. Unmaintained and mostly empty.
12. BrainFlow Android AAR: "MIT" leaves out the SimpleBLE terms.

Facts confirmed, recommendation lowered: the Lee and Ahn dataset and PPG-DaLiA (adopt to
evaluate), ROAMM and muse.js (evaluate to learn-from), sqlite-vec (evaluate to skip).

## 6. Proposed corrections to existing documents

None of these has been made. Each is a proposal for its owner to accept or reject.

**`docs/ROADMAP.md`**

- 003: name the feature ("aperiodic exponent") and drop "(fooof)". Give the golden-file gate a
  tolerance policy. Say "pulse-based" variability.
- 004: the row still says the optics order has "two competing hypotheses". It is settled as wire
  order and confirmed per unit by check F1.
- 005: "hotkey now" is a new component, not an extension of `keys.py`. "BLE ring later" arrives as
  an OS keyboard, not through bleak.
- 006 and the Phase 0 exit: two weeks of probes give about 60 labels, which is too few to judge an
  interpreter (3.7).
- 007 and 013: say sherpa-onnx 2.0 or later, and name turn-taking as a deliverable. The crisis path
  should say which country it serves.
- 009: the scripts must be written originally. Consider peak-to-trough swing for the gate.
- 010: the roadmap names no Bluetooth package. When its spec is written, plan on universal_ble.

**`docs/KNOWN-ISSUES.md`** (ear sensors)

- Add a fourth possible cause: the electrical contacts between the pod and the band.
- Add to "What to try": more pressure over the ear pads, several minutes of settling, reseating
  the pod, and possibly a thin smear of electrode gel. P0 and H8 stay as they are.

**`docs/research/2026-11-25-stack-review.md`**

- "Bandpass 1 to 40 Hz and a 60 Hz notch before features" harms the aperiodic fit.
- "Record to Parquet (or XDF via LSL)" is outdated: the format built is append-only float64 with a
  JSON manifest.
- sqlite-vec needs its caveats, and FTS5 is enough for Phase 0.
- "Encrypt at rest" needs a scope: the database only, not the recordings.
- A HID ring through bleak will not work on Windows.
- arXiv 2510.20958 is not a thought-probe study.
- "0.50 to 0.85 accuracy per person" is the range of individuals in one 128-channel study, whose
  means were 0.64 and 0.69.
- The ONNX recommendation needs the 3.15 caveat. flutter_edge_ai is at 2.7.2. Piper is no longer
  MIT. sherpa-onnx needs "2.0 or later". Ollama needs its three conditions.
- flutter_blue_plus needs the licence note and a replacement.

**`docs/research/2026-11-26-muse-docs-and-oss-survey.md`**

- Add the BrainFlow 5.24.0 signal-quality and streaming additions.
- Soften "The DRL/REF stream would show on the head directly": it is one unit's measurement.
- Cite the two open threshold comparisons (3.2).
- Add the SimpleBLE version and licence terms.

**`docs/research/2026-11-25-athena-fnirs-resources.md`**

- Stream 0x53 runs at about 30 Hz as measured (about 25 Hz on 3.1.29).
- The body still reads as if the Mind Monitor order were the default.
- NeuroKit2 is at 0.3.0 and is a test oracle only. Cedalion cannot be installed beside MuFuse.
- OpenMuse: "MIT in package metadata, no LICENSE file".
- The list of other decoders is missing the Elata SDK, NeuroSkill and neurofeed.

**`reports/Muse EEG self awareness research.md`**

- ds001787 and ds007216 are CC0.
- The cross-person range of 0.57 to 0.70 AUC is optimistic at the top.
- The manifest example uses `min_channels_good: 3` and a feature from the ear sensors, which
  conflicts with KNOWN-ISSUES: it needs 2 and forehead-only features.
- "Retire if AUC ≤ 0.55 after 40 labels" is statistically too weak.
- "No validated non-LLM risk classifier" is partly outdated (the Suicide Risk Lexicon).

**Elsewhere**

- `docs/design/2026-11-26-companion-experience.md` names Flutter for the desk strip and no
  Bluetooth package or fallback. If a Python-only fallback is ever wanted, pywebview (BSD-3) and
  NiceGUI (MIT) are permissively licensed; PySide6 is LGPL (3.6, 3.10).
- Any mention of NEUROFUSION's Fusion as an open-source comparable is dead: the repository
  returns 404.
- The cause of duplicate timestamps can be stated in `timing.py`: BrainFlow returns the current
  time whenever its computed stamp would not advance.

## 7. What could not be reached

- The Mind Monitor forum refuses automated fetching. Everything attributed to it here came
  through search snippets.
- No openly licensed defusion or urge-surfing script was found.
- No dataset with a Muse-class headband and thought probes was found.
- No validation of any beat detector on forehead PPG from the Athena was found, other than what
  the Ravi dataset would allow us to do ourselves.
