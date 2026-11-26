# Open-Source Libraries and Pretrained Models for EEG / fNIRS / PPG Interpretation (Muse S Athena toolkit map, as of late Nov 2026)

Scope note: Version and release dates below come from a live PyPI JSON query run on 2026-11-25 (one call per package). Items marked "(prior knowledge, not re-verified this session)" are from the researcher's background knowledge and should be checked before being relied on; they are kept out of Cited Findings.

## Core signal processing (MNE, MNE-NIRS, BrainFlow DataFilter, NeuroKit2, HeartPy, pyHRV, YASA, autoreject, ASR, blink/EMG)

### Takeaway
The core Python stack is healthy and actively released in 2026 (MNE 1.13, NeuroKit2 0.3.0, YASA 0.8.1, autoreject 0.5.2, BrainFlow 5.24, all BSD/MIT). HeartPy is effectively abandoned (last release 2021), MNE-NIRS is slower-moving (last release Oct 2025), and ASR for Python (asrpy 0.0.8) is still pre-1.0. None of these are ONNX/mobile libraries; they belong in Phase 0 (desktop Python) and their logic must be re-implemented (or simplified) in Dart/C++ for Phase 1. YASA has no direct validation on Muse channels; frontal single-channel staging is limited mainly by channel topology.

### Cited Findings
- MNE-Python latest release 1.13.2, uploaded 2026-09-11, BSD-3-Clause — [PyPI mne](https://pypi.org/project/mne/)
- MNE-NIRS latest release 0.7.3, uploaded 2025-10-16, BSD-3-Clause (slower cadence than core MNE; ~13 months without a release at time of query) — [PyPI mne-nirs](https://pypi.org/project/mne-nirs/)
- BrainFlow latest release 5.24.0, uploaded 2026-11-08 (user is on 5.22; two minor versions behind) — [PyPI brainflow](https://pypi.org/project/brainflow/)
- NeuroKit2 latest release 0.3.0, uploaded 2026-11-01, MIT — [PyPI neurokit2](https://pypi.org/project/neurokit2/)
- HeartPy latest release 1.2.7, uploaded 2021-03-20 — no release in ~5.7 years; treat as abandoned — [PyPI heartpy](https://pypi.org/project/heartpy/)
- pyHRV latest release 0.5.0, uploaded 2026-06-17 (revived after a long gap; previous release line was 0.4.x) — [PyPI pyhrv](https://pypi.org/project/pyhrv/)
- YASA latest release 0.8.1, uploaded 2026-10-25, BSD-3-Clause — [PyPI yasa](https://pypi.org/project/yasa/)
- autoreject latest release 0.5.2, uploaded 2026-11-04, BSD-3-Clause — [PyPI autoreject](https://pypi.org/project/autoreject/)
- PyPREP 0.10.0 (2026-10-27, MIT) and mne-icalabel 0.10.0 (2026-10-05, BSD-3) are actively released — [PyPI pyprep](https://pypi.org/project/pyprep/); [PyPI mne-icalabel](https://pypi.org/project/mne-icalabel/)
- asrpy (Python Artifact Subspace Reconstruction) latest 0.0.8, uploaded 2025-06-19, BSD-3 — still pre-1.0 — [PyPI asrpy](https://pypi.org/project/asrpy/)
- meegkit (includes ASR, denoising tools) latest 0.2.0, uploaded 2026-07-20, BSD-3 — [PyPI meegkit](https://pypi.org/project/meegkit/)
- No published study directly tests YASA on Muse data. A 2026 medRxiv preprint evaluating YASA and Dreamento on the Zmax headband frontal channel (F7-Fpz) against manual PSG found that signal quality metrics did not predict staging performance within adequate recordings, "indicating that channel topology is the primary limiting factor for frontal single-channel staging" — [medRxiv 2026 preprint](https://www.medrxiv.org/content/10.64898/2026.06.01.26354591v1.full.pdf)
- YASA's own validation used central + EOG + EMG channels (C4-A1, LOC-A2, Chin1-Chin2), not frontal/behind-ear channels — [YASA validation, PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7751170) (as summarized by search; see Gaps)
- A Muse-S sleep validation reported 88–96% accuracy across stages (sensitivity 79–92%, specificity 90–99%) using Muse's own automated algorithm, not YASA — [Springer 2026 article](https://link.springer.com/10.1007/s44470-026-00059-x)
- A 2-channel Sleep-EDF (Fpz-Cz, Pz-Oz) wake-vs-sleep experiment showed fold AUROC standard deviations of about ±12–14 points for all models including the classical baseline, attributed to subject heterogeneity — [arXiv 2607.24519](https://arxiv.org/html/2607.24519v1)

### Inferences
- For Phase 0, MNE (data containers, filtering, PSD) + NeuroKit2 (PPG peak detection, HRV, EEG/EOG utilities) + YASA (bandpower, sleep features) + autoreject (thresholds) is a well-maintained, permissively licensed core. Replace HeartPy with NeuroKit2 or pyHRV.
- autoreject, PyPREP, ICA/ICLabel and ASR all assume many channels; with 4 dry channels, ICA is nearly useless (at most 4 components) and ASR's covariance-based reconstruction has very little spatial redundancy to work with. A simpler, portable approach is more appropriate: per-window amplitude/variance/kurtosis thresholds, a line-length or high-frequency (>30–40 Hz) power index for EMG (jaw clench is strong at TP9/TP10), AF7/AF8 low-frequency large deflections for blinks/eye movements, and IMU-based motion gating. These are trivial to port to Dart/ONNX.
- YASA's pretrained staging classifier expects a central EEG (plus optional EOG/EMG). AF7/AF8 can act as a crude EOG proxy, and TP9/TP10 pick up some EMG, but expect degraded and unvalidated accuracy; treat YASA staging on Muse as experimental, and validate against your own sleep diary or a second device.
- MNE-NIRS assumes standard source-detector montages and SNIRF-style data; the Athena's raw optical channels need custom extraction (wavelength separation, modified Beer-Lambert) before MNE-NIRS functions become meaningful. MNE-NIRS's slower cadence is not a blocker but suggests limited new features.
- BrainFlow DataFilter (C++ core with Python, C#, Java, Julia, Rust, etc. bindings) is the most portable option for porting filtering/band-power logic to a Flutter app via FFI (prior knowledge, not re-verified this session: BrainFlow's core is C/C++ and is MIT-licensed).

### Gaps
- No direct published accuracy figure for YASA on Muse (TP9/AF7/AF8/TP10) channels was found.
- Licenses for HeartPy, pyHRV, YASA's metadata fields and BrainFlow were blank/non-standard in PyPI metadata; check the GitHub LICENSE files.
- Did not verify whether NeuroKit2 0.3.0 changed APIs relative to 0.2.x.
- Did not find a maintained, validated ASR implementation targeting 2–4 channel dry EEG.

## Feature extraction and classical ML (pyRiemann, MNE-Features, antropy, fooof/specparam)

### Takeaway
All four are maintained and permissively licensed. specparam 2.0 is still a release candidate (rc7, June 2026); fooof 1.1.1 is the stable line and is numerically equivalent for the same settings. Riemannian/covariance methods and spectral features are the strongest calibration-light baselines; recent benchmarks show simple band-power features are frequently not beaten by foundation models.

### Cited Findings
- pyRiemann latest release 0.12, uploaded 2026-07-01, BSD-3 — [PyPI pyriemann](https://pypi.org/project/pyriemann/)
- MNE-Features latest release 0.3.2, uploaded 2026-02-11, BSD-3 — [PyPI mne-features](https://pypi.org/project/mne-features/)
- antropy (entropy/complexity features) latest 0.2.3, uploaded 2026-10-17, BSD-3 — [PyPI antropy](https://pypi.org/project/antropy/)
- fooof stable 1.1.1 (2025-05-05, Apache-2.0); specparam latest 2.0.0rc7 (2026-06-09, Apache-2.0) — [PyPI fooof](https://pypi.org/project/fooof/); [PyPI specparam](https://pypi.org/project/specparam/)
- specparam is "currently available as a 'release candidate'", may contain breaking changes; the main new feature is support for time-resolved and event-related analyses; no changes to default settings/models; "background" renamed "aperiodic" and "slope" renamed "exponent" — [specparam changelog](https://specparam-tools.github.io/changelog.html)
- Project docs suggest existing fooof users "might as well stick with that, unless any of the new functionality in specparam is particularly important" — [fooof changelog](https://fooof-tools.github.io/fooof/changelog.html)
- In a controlled Oct 2026 evaluation, "no model beat a five-band log-power baseline on emotion or motor imagery tasks" — [arXiv 2610.32067](https://arxiv.org/abs/2610.32067)
- On 2-channel sleep EEG, a logistic regression on classical features (AUROC 68.6%) was not beaten by CBraMod (68.3%), EEGMamba (68.1%), REVE-Base (62.3%) or LaBraM (58.1%) — [arXiv 2607.24519](https://arxiv.org/html/2607.24519v1)

### Inferences
- For alpha interpretation on Muse, specparam/fooof is important: a shift in the 1/f aperiodic exponent (e.g., with arousal, drowsiness, or EMG contamination at TP9/TP10) changes absolute alpha band-power without a true oscillatory change. Report "periodic alpha peak power above aperiodic fit" and "alpha peak frequency" rather than raw 8–12 Hz power. Use fooof 1.1 for stability now; migrate to specparam 2.0 when it reaches final.
- specparam fitting is iterative curve fitting (scipy) and is not directly ONNX-exportable; for Phase 1 compute it on desktop or approximate it on-device with a robust linear fit of log-power vs log-frequency excluding peak bands (a simple "FOOOF-lite"), which is easy to implement in Dart.
- pyRiemann with 4 channels gives 4x4 covariance matrices (10 unique tangent-space features), cheap enough for phones. Tangent-space features + logistic regression can be exported via skl2onnx after manually computing the tangent-space projection; the matrix log/sqrt for a 4x4 SPD matrix is easy to implement natively (prior knowledge: pyRiemann estimators are scikit-learn compatible; not re-verified this session).
- Feature set recommendation for a 4-channel dry setup: per-channel log band powers (delta–gamma), relative powers, frontal asymmetry (AF8 vs AF7 alpha), aperiodic exponent/offset, alpha peak frequency, a few antropy measures (permutation/spectral entropy, Hjorth), covariance/coherence between AF7–AF8 and TP9–TP10, plus artifact indices.

### Gaps
- Did not verify whether pyRiemann 0.12 ships built-in Euclidean alignment / Riemannian Procrustes transformers (search returned method papers, not API docs).
- No published validation of specparam on Muse data was found in this session.

## Deep learning toolkits (Braindecode, MOABB, TorchEEG, small on-device models)

### Takeaway
Braindecode is the most active hub (2.1.0 released 2026-11-23; v2.0 overhauled channel-flexible handling and Hugging Face integration and includes many foundation models), MOABB is maintained for benchmarking, and TorchEEG has not released since Dec 2024. No source confirmed first-class ONNX export in Braindecode; small CNNs like EEGNet are standard PyTorch and should export via torch.onnx, but that is not documented by the projects in what was found.

### Cited Findings
- Braindecode latest release 2.1.0, uploaded 2026-11-23, BSD-3-Clause — [PyPI braindecode](https://pypi.org/project/braindecode/)
- Braindecode "What's new" page (as fetched) listed 2.0.0 as current, dated 2026-11-02 — docs lag PyPI — [Braindecode whats_new](https://braindecode.org/stable/whats_new.html)
- Braindecode 2.0.0 notes: `channel_strategy` (e.g., `"spline"`) replaces removed `Interpolated*` model classes; `ch_mask` and `pad_channels_collate()` let some models mix recordings with different channel counts in one batch; `resolve_channel_positions()` maps channel names to positions with an `on_missing` option; ZUNA and NeuroRVQ can handle channels lacking a pretrained slot — [Braindecode whats_new](https://braindecode.org/stable/whats_new.html)
- Braindecode 2.0.0 models referenced include LaBraM (mean-pooling default changed), BENDR (final LayerNorm removed; 1.x checkpoints load but predict differently), REVE, LUNA, EEGPT, BIOT, CBraMod, ZUNA, BrainBERT, "Guetschel2026" (encoder for 58 MAE/JEPA checkpoints), DuIN; `from_pretrained`/`push_to_hub` Hugging Face integration; requires PyTorch/TorchAudio ≥2.6. ONNX and torch.export not mentioned in the visible notes — [Braindecode whats_new](https://braindecode.org/stable/whats_new.html)
- Braindecode's EEGNet Hugging Face repo is "architecture-only"; "no pretrained weights are distributed here", and pretrained checkpoints carry their own licence terms — [HF braindecode/EEGNet](https://huggingface.co/braindecode/EEGNet/blob/main/README.md)
- Braindecode v1.2.0 Zenodo record dated 2025-12-23 — [Zenodo](https://zenodo.org/records/17699192)
- A 2025 EEG challenge paper describes Braindecode as a PyTorch model zoo with over 30 deep learning models including EEGNet, BIOT and LaBraM — [arXiv 2506.19141](https://arxiv.org/pdf/2506.19141)
- MOABB latest 1.7.2, uploaded 2026-09-14, BSD-3 — [PyPI moabb](https://pypi.org/project/moabb/)
- TorchEEG latest 1.1.3, uploaded 2024-12-23, MIT — ~11 months without release — [PyPI torcheeg](https://pypi.org/project/torcheeg/)
- onnxruntime latest 1.32.0, uploaded 2026-11-13, MIT — [PyPI onnxruntime](https://pypi.org/project/onnxruntime/)

### Inferences
- For Phase 1 on-device inference, small CNNs (EEGNet ~ a few thousand params, ShallowFBCSPNet, small TCNs) built in Braindecode and exported with `torch.onnx.export` are the realistic target; they have fixed input shapes (4 channels x N samples), use standard ops (conv, depthwise conv, batch norm, ELU, pooling) that ONNX Runtime Mobile supports. Verify export by running the ONNX model in onnxruntime against PyTorch outputs.
- Braindecode 2.0's breaking changes (LaBraM pooling default, BENDR LayerNorm) mean pin the version and record it with any checkpoint.
- TorchEEG is usable but appears to be in a slow/stalled phase; prefer Braindecode for new work.
- MOABB is mainly useful for benchmarking pipelines on public BCI datasets; few of its datasets resemble Muse placement, so its value here is methodology (cross-session evaluation) rather than directly transferable models.

### Gaps
- No source found confirming documented ONNX export support (or tested ops coverage) in Braindecode 2.x.
- Braindecode 2.1.0 release notes were not visible on the fetched docs page.
- No public pretrained EEGNet-style weights trained on Muse-like (TP9/AF7/AF8/TP10, dry) data were found.

## EEG foundation models (LaBraM, BENDR, CBraMod, EEGPT, BIOT, NeuroLM, REVE, LUNA, successors)

### Takeaway
Several 2025–2026 models claim arbitrary-montage support (CBraMod via ACPE, REVE via 4D positional encoding, LUNA, ZUNA in Braindecode), so feeding 4 channels is technically possible. But independent 2026 controlled evaluations find benefits are small or absent under fair controls: random-init encoders often match pretraining, band-power baselines are often not beaten, and on 2-channel data no FM beat a classical baseline. For a 4-channel dry consumer device, foundation models are a research experiment, not a Phase 1 dependency.

### Cited Findings
- Benchmarks: EEG-FM-Bench evaluates seven FMs including LaBraM and CBraMod on 14 downstream tasks — [arXiv 2508.17742](https://arxiv.org/pdf/2508.17742); OmniEEG-Bench (June 2026) reports CBraMod and LaBraM ranking 1st/2nd under full fine-tuning, and CBraMod, REVE and BrainOmni top-3 under linear probing — [arXiv 2606.00815](https://arxiv.org/html/2606.00815v1); NeuroAtlas (May 2026) also benchmarks clinical/BCI FMs — [arXiv 2605.14698](https://arxiv.org/html/2605.14698v1); AdaBrain-Bench — [arXiv 2507.09882](https://arxiv.org/pdf/2507.09882)
- Controlled evaluation (Jeon, Cho, Suh; submitted 2026-10-23) of five public EEG FMs + an in-house JEPA model: choosing probe layer by test score inflated peaks by +0.034 on average; with validation-selected layers, random initialization matched or beat pretraining for half the models on sleep and emotion tasks; no model beat a five-band log-power baseline on emotion or motor imagery; under full fine-tuning only 5 of 30 model-task pairs improved beyond twice seed variation; one -0.290 AUROC loss persisted — [arXiv 2610.32067](https://arxiv.org/abs/2610.32067)
- 2-channel Sleep-EDF wake-vs-sleep with frozen probes, LOSO: Classical LogReg AUROC 68.6%; EEGMamba (3.3M params) 68.1%; CBraMod (4.9M) 68.3%; REVE-Base (69.4M) 62.3%; LaBraM (5.8M) 58.1%. "No foundation model outperforms classical features in the specific 2-channel binary Sleep-EDF experiment." REVE's result is confounded because bipolar channel names had to be resolved to single electrodes for its 4D positional encoding; the paper notes limited spatial coverage hurts positional encodings — [arXiv 2607.24519](https://arxiv.org/html/2607.24519v1)
- CBraMod accepts arbitrary channel configurations via ACPE (asymmetric conditional positional encoding); LaBraM supports heterogeneous montages but requires correct channel-to-embedding mapping; pretraining-hour figures for CBraMod differ across sources (~9,000 cleaned TUEG hours vs ~27,000 hours) — [CBraMod arXiv 2412.07236](https://arxiv.org/pdf/2412.07236); [NeuroAtlas](https://arxiv.org/html/2605.14698v1) (as summarized by search)
- REVE (NeurIPS 2025): 4D positional encoding "enables it to process signals of arbitrary length and electrode arrangement"; pretrained on >60,000 hours from 92 datasets / 25,000 subjects — [arXiv 2510.21585](https://arxiv.org/html/2510.21585v1); [NeurIPS 2025](https://neurips.cc/virtual/2025/poster/117334)
- REVE weights on Hugging Face (reve-small, reve-base, reve-large) require 200 Hz input, require agreeing to data-usage terms, and are under the custom "REVE Responsible Use License v1.0" (allows research/commercial/personal use; prohibits privacy intrusion, re-identification, non-consensual surveillance/profiling) — not a standard OSI license; a third-party Rust wrapper `reve-rs` is Apache-2.0 for its code only — [HF brain-bzh/reve-small](https://huggingface.co/brain-bzh/reve-small); [reve-rs](https://docs.rs/crate/reve-rs/latest/source/README.md)
- NeuroLM (ICLR 2025): unifies EEG tasks via instruction tuning on an LLM; largest variant 1.7B params; pretrained on ~25,000 hours EEG; evaluated on six tasks (abnormal detection, event type classification, etc.); authors note larger models are more prone to overfitting, which may explain degradation on some datasets; builds on LaBraM's tokenizer — [arXiv 2409.00101](https://arxiv.org/pdf/2409.00101); [ICLR 2025 proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/file/8b4add8b0aa8749d80a34ca5d941c355-Paper-Conference.pdf)
- Braindecode 2.0 provides implementations/checkpoint loading for LaBraM, BENDR, CBraMod, EEGPT, BIOT, REVE, LUNA, ZUNA, BrainBERT and others — [Braindecode whats_new](https://braindecode.org/stable/whats_new.html); braindecode also hosts an EEGPT model card on HF — [HF braindecode/EEGPT](https://huggingface.co/braindecode/EEGPT/blob/main/README.md)
- A 2025 critical review of brain-signal FMs exists — [arXiv 2507.11783](https://arxiv.org/html/2507.11783v1)

### Inferences
- Channel flexibility is necessary but not sufficient: Muse's TP9/TP10 behind-ear sites and AF7/AF8 are present in 10-10/10-20 extended coordinate sets, so position-based models (REVE, CBraMod, LUNA) can accept them; however, pretraining corpora (mostly TUH clinical wet-gel EEG, BCI lab data) contain few dry, forehead/ear-only recordings, and the Muse reference (Fpz) differs from typical clinical references. Expect a domain gap.
- Size: CBraMod (~4.9M) and LaBraM-base (~5.8M) are small enough for ONNX on phones in principle; REVE-Base (69M) is borderline; NeuroLM (up to 1.7B) is not practical on-device. Transformer ops export to ONNX generally, but custom positional-encoding code may need tracing work (unverified).
- Realistic benefit: use FMs as frozen feature extractors in a Phase 0 experiment, always compared against (a) a band-power + logistic regression baseline and (b) a randomly-initialized copy of the same encoder, using cross-session (not within-session) validation. Only ship one if it clearly wins.
- Licenses vary per checkpoint (REVE custom RUL; many academic repos are MIT/unspecified); check each HF repo's LICENSE before redistribution in an app.

### Gaps
- Did not individually verify licenses, parameter counts, or HF availability for LaBraM, CBraMod, EEGPT, BIOT, BENDR, LUNA, ZUNA in this session.
- Which specific models were tested in arXiv 2610.32067 was not visible on the abstract page (search summary mentions LaBraM, CBraMod, EEGPT, LUNA, LuMamba but this was not confirmed from the paper text).
- No study found that evaluates any FM on Muse or other 4-channel dry consumer headband data.
- No source confirmed ONNX export of any EEG FM.

## EEG-to-language / LLM bridging (NeuroLM, Thought2Text, EEG-to-text)

### Takeaway
Open-vocabulary EEG-to-text claims are largely not credible: a 2024 critique and multiple 2026 follow-ups show many models perform as well on pure noise as on EEG, with scores inflated by teacher forcing and BLEU/stopword matching. "EEG-LLM" models like NeuroLM are really multi-task classifiers with a language interface, trained on dense clinical EEG. For this app, the useful and honest bridge is: classical/learned classifiers produce structured state summaries (with confidence and signal quality), and the local LLM narrates those — not raw EEG-to-language.

### Cited Findings
- "Are EEG-to-Text Models Working?" (Jo et al., 2024): prior work used implicit teacher forcing during evaluation, artificially inflating metrics, and lacked a pure-noise baseline; models achieved similar or better performance on pure noise than on EEG — [arXiv 2405.06459](https://arxiv.org/html/2405.06459v4)
- ACL 2026 paper: under teacher-forced evaluation some EEG2Text systems perform comparably when fed random noise, while failing to generate meaningful decoding without teacher forcing; proposes a teacher-forcing-free protocol — [ACL 2026 long.61](https://aclanthology.org/2026.acl-long.61.pdf)
- "Escaping the BLEU Trap" (2026): models can achieve competitive BLEU by matching stopwords/templates; when teacher forcing is removed, prior models show "full signal neglect" — [arXiv 2603.03312](https://arxiv.org/html/2603.03312)
- "Is EEG-to-Text Feasible in Real-World Scenarios?" (2026) proposes a neuropsychology-inspired benchmark and warns that teacher-forcing-free BLEU/ROUGE/WER alone weakens sensitivity to EEG-vs-noise controls — [arXiv 2607.18749](https://arxiv.org/pdf/2607.18749)
- A survey recommends noise-baseline testing with matching dimensionality, significance testing with confidence intervals/effect sizes, and non-teacher-forced evaluation — [arXiv 2502.12048](https://arxiv.org/pdf/2502.12048)
- Thought2Text: captures EEG during visual stimuli, encodes with a multichannel encoder, generates text with instruction-tuned LLMs; evaluated with standard NLG metrics plus fluency/adequacy — [arXiv 2410.07507](https://arxiv.org/html/2410.07507); a 2026 paper notes its reliance on visual stimuli/image representations restricts expressive freedom — [arXiv 2605.17503](https://arxiv.org/pdf/2605.17503)
- NeuroLM frames EEG tasks as instruction-following text outputs (classification labels via an LLM) rather than free-form thought decoding — [arXiv 2409.00101](https://arxiv.org/pdf/2409.00101)

### Inferences
- Nothing in this literature transfers to 4 dry channels during free-living use; datasets (e.g., ZuCo, image-viewing EEG) use 64–128 channel research caps and stimulus-locked paradigms.
- Practical design for the app's LLM layer: emit a compact JSON/text summary per epoch or session (e.g., "relaxed-alert index rising, frontal alpha asymmetry +0.12, HR 62 bpm, HRV RMSSD 48 ms, signal quality: good 85%, EMG contamination TP9 high"), with explicit uncertainty and data-quality flags, and instruct the LLM never to infer thoughts/content. This sidesteps the hype and keeps the LLM honest.
- If any "EEG embedding to LLM" experiment is attempted, require a noise/shuffled-EEG control and a randomly-initialized-encoder control as gating tests.

### Gaps
- No direct 2026 critique specific to Thought2Text was found; whether it reports a noise baseline was not verified.
- No EEG-LLM model trained on consumer few-channel data was found.

## Streaming / real-time frameworks (LSL, mne-lsl, Timeflux, MetaBCI, BCI2000, OpenViBE, NeuroPype, neurofeedback)

### Takeaway
LSL (pylsl 1.19.0, released 2026-11-24) and mne-lsl (1.15.0, 2026-11-12) are actively maintained and are the right Phase 0 glue; OpenMuse already streams via mne-lsl. Timeflux has not released since Dec 2024 (stalling); MetaBCI is active but GPL-2.0 (license-incompatible with closed app distribution). BCI2000/OpenViBE/NeuroPype are heavyweight lab or commercial tools of limited relevance for a Flutter mobile app.

### Cited Findings
- pylsl latest 1.19.0, uploaded 2026-11-24 — [PyPI pylsl](https://pypi.org/project/pylsl/)
- mne-lsl latest 1.15.0, uploaded 2026-11-12, BSD-3-Clause — [PyPI mne-lsl](https://pypi.org/project/mne-lsl/)
- OpenMuse uses MNE-LSL (`mne_lsl.lsl`) as an improved Python binding to the LSL C++ library, replacing pylsl — [OpenMuse GitHub](https://github.com/DominiqueMakowski/OpenMuse)
- Timeflux latest 0.17.2, uploaded 2024-12-04, MIT — ~12 months without release — [PyPI timeflux](https://pypi.org/project/timeflux/)
- MetaBCI latest 0.2.0, uploaded 2026-01-11, license GPL-2.0 — [PyPI metabci](https://pypi.org/project/metabci/)
- muselsl latest 2.5.3, uploaded 2026-09-08, BSD-3 — [PyPI muselsl](https://pypi.org/project/muselsl/)

### Inferences
- Phase 0: OpenMuse or BrainFlow -> LSL -> mne-lsl `StreamLSL` ring buffer -> windowed feature extraction -> classifier -> summary. Record raw streams to XDF (LabRecorder) for offline replay so the same pipeline can be tested deterministically.
- Phase 1: LSL is not needed inside the Flutter app (single process); acquisition via BLE directly (or BrainFlow C++ via FFI) into an in-app ring buffer, features in Dart/C++, classifier via ONNX Runtime. LSL is still useful in desktop builds for interoperability (LabRecorder, other tools).
- Closed-loop neurofeedback: the frameworks above add little beyond a simple sliding-window loop for a single-user app; latency budget is dominated by BLE packetization and window length (e.g., 1–2 s windows with 0.25 s hop).
- MetaBCI's GPL-2.0 license means copying its code into a distributed app would impose GPL obligations; use it only as a reference.

### Gaps
- Did not verify current status/releases of BCI2000, OpenViBE, NeuroPype, or any dedicated neurofeedback framework (e.g., NFBLab, PyNFB) in this session.
- Did not verify whether liblsl has official Android/iOS builds usable from Flutter.

## Muse-specific community tools (OpenMuse, muse-lsl, Mind Monitor, muse-rs, amused) and Athena fNIRS pipelines

### Takeaway
OpenMuse (Dominique Makowski) is the most capable open tool for the Athena: it decodes EEG (4 + 4 aux @256 Hz), optics presets (Optics4/8/16 @64 Hz) and IMU, and streams via LSL. But its own roadmap lists PPG and fNIRS signal extraction as not yet validated, and no license is shown on the README. muse-lsl now has an Athena optics flag. There is no validated open-source Athena fNIRS (HbO/HbR) pipeline; the only one found is a single-author R-script preprint.

### Cited Findings
- OpenMuse: record/stream (LSL)/view tool for Muse S Athena; not an official InteraXon product; "experimental software for research use only"; CLI commands `find`, `record`, `stream`, `view`; multi-device (hyperscanning) support; 108 stars, 28 forks, 423 commits, no tagged releases shown; license not shown on README; Windows support not mentioned — [OpenMuse GitHub](https://github.com/DominiqueMakowski/OpenMuse)
- OpenMuse specs: EEG TP9/AF7/AF8/TP10 + 4 amplified aux channels at 256 Hz, 14-bit (presets EEG4/EEG8); triple-wavelength PPG (IR 850 nm, near-IR 730 nm, red 660 nm) and a 5-optode bilateral frontal fNIRS sensor at 64 Hz, 20-bit (presets Optics4/8/16); accelerometer and gyroscope at 52 Hz, 16-bit — [OpenMuse GitHub](https://github.com/DominiqueMakowski/OpenMuse)
- OpenMuse roadmap open items: "Validate the best PPG signal extraction method", "Validate fNIRS signal extraction method", timestamp accuracy validation for ERPs, battery streaming; presets are "derived from the signature of the data packets" and "more presets could exist" — [OpenMuse GitHub](https://github.com/DominiqueMakowski/OpenMuse)
- muse-lsl exposes Athena optical (fNIRS) data via a `-o/--optics` flag; latest release 2.5.3 (2026-09-08) — [muse-lsl GitHub](https://github.com/alexandrebarachant/muse-lsl); [PyPI muselsl](https://pypi.org/project/muselsl/)
- muse-rs (Rust) README notes Athena PPG data is received but not yet decoded (version 0.0.1) — [muse-rs docs.rs](https://docs.rs/crate/muse-rs/0.0.1/source/README.md)
- `amused` is a PyPI package described as an open-source Python library for streaming data from Muse S (Athena) headbands — [PyPI amused](https://pypi.org/project/amused/); [depscope](https://depscope.dev/pkg/pypi/amused)
- A community test repo exists for Athena — [muse-athena-test](https://github.com/OliverACollins/muse-athena-test)
- Athena fNIRS pipeline preprint (Paolo Maccallini, Zenodo, v2 2026-06-15, CC BY 4.0): theory of frontal hemoglobin measurement applied to the Athena; describes an R script estimating resting-state relative HbO/HbR from five-minute recordings; 9 months of personal recordings correlated with a subjective cognitive measure; only a PDF is attached (script not linked) — [Zenodo 20705110](https://zenodo.org/records/20705110)
- Muse markets the Athena's fNIRS as enabling monitoring of the prefrontal cortex — [IEEE Spectrum](https://spectrum.ieee.org/muse-headband); [Engadget](https://www.engadget.com/wearables/muses-new-wearable-eeg-knows-how-hard-youre-thinking-120041154.html)

### Inferences
- For Phase 0, BrainFlow (user's current choice) and OpenMuse are complementary: use OpenMuse's packet decoding and channel documentation as a cross-check of BrainFlow's Athena optics mapping (wavelength/channel order), since both are reverse-engineered.
- Because optics extraction is unvalidated in all open tools, treat fNIRS-derived "oxygenation" as an experimental trend metric (relative, within-session changes), with motion (IMU) and PPG/cardiac components regressed out; PPG-derived heart rate/HRV is more mature and should be prioritized.
- Absence of a visible license on OpenMuse means it should not be vendored into a distributed app until the license is confirmed.
- Mind Monitor (closed-source paid app) and Petal Metrics are not open-source; they are useful only as reference/exports (prior knowledge, not re-verified).

### Gaps
- OpenMuse license and Windows support not confirmed; last-commit date not visible.
- No information found on Mind Monitor's or Petal Metrics' current Athena support or maintenance status.
- No validated open-source HbO/HbR computation for Athena optics found; the Zenodo preprint's R script is not public.
- Did not determine exactly how many optical channels map to which wavelengths/source-detector distances.

## Personalization / calibration for few-channel data (transfer learning, Euclidean alignment, few-shot)

### Takeaway
The most practical, well-established tools are covariance re-centering methods: Euclidean Alignment (EA), Riemannian re-centering / Procrustes Analysis (RPA), and tangent-space alignment, which need only unlabeled (or minimally labeled) data from a new session and are cheap for 4x4 covariances. Pair with per-user baseline normalization (z-scoring features against a resting baseline) and small-head fine-tuning rather than full model fine-tuning.

### Cited Findings
- Euclidean Alignment (He & Wu, 2019) aligns trials from different subjects in Euclidean space as a pre-processing step usable with any downstream classifier; in their comparison it beat a Riemannian alignment method and no-alignment approaches — [arXiv 1808.05464](https://arxiv.org/html/1808.05464)
- A systematic evaluation of EA with deep learning notes EA's ease of use, low computational complexity and compatibility with DL models — [arXiv 2401.10746](https://arxiv.org/html/2401.10746v4)
- Riemannian Procrustes Analysis adds stretching (to equalize dispersion between domains) and rotation (to align class centers of mass) after re-centering — [Frontiers 2022 / Bleuzé et al.](https://www.frontiersin.org/journals/human-neuroscience/articles/10.3389/fnhum.2022.1049985/pdf)
- Tangent Space Alignment (Bleuzé, Mattout, Congedo, 2022) reports a 2.7% global accuracy improvement over RPA across 18 BCI databases, handles datasets with different channel counts, and requires only one SVD — [PMC9755175](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9755175/)
- Riemannian transfer learning is framed as a way to use minimal calibration data from a user; benchmark tooling lacked cross-subject transfer evaluation support — [arXiv 2111.12071](https://arxiv.org/pdf/2111.12071v1.pdf)
- Validation-protocol choices (e.g., selecting layers by test score) materially inflate reported gains (+0.034 avg) — [arXiv 2610.32067](https://arxiv.org/abs/2610.32067)

### Inferences
- Recommended personalization stack for MuFuse: (1) each session starts with a 1–2 min eyes-closed/eyes-open baseline; (2) compute the session reference covariance and apply EA/re-centering (a 4x4 inverse square root — trivial on-device); (3) z-score spectral features against the user's rolling baseline; (4) train a small user-specific head (logistic regression or tiny MLP) on top of population features, updated with self-labels (e.g., post-session ratings); (5) evaluate strictly cross-session.
- Since this is a single-user app, "cross-subject transfer" matters less than cross-session drift (headband placement, skin contact, hair, sweat with dry electrodes); re-centering per session targets exactly this drift.
- Few-shot fine-tuning of FMs is unlikely to beat these methods given the controlled-evaluation results above.

### Gaps
- Did not confirm which alignment transformers are built into pyRiemann 0.12 (e.g., re-centering/stretching/rotation classes) or Braindecode 2.x.
- No study found evaluating EA/RPA specifically on 4-channel dry consumer EEG.
