# Open Datasets for a Muse S Athena-style Self-Awareness Model (EEG TP9/AF7/AF8/TP10 + forehead fNIRS/PPG + IMU)

Notes compiled 2026-11-25. Research budget was limited (about 30 tool calls), so some license fields could not be verified directly. Each entry says whether a field was verified, comes from a secondary source, or is unverified.

Shorthand used below: **PT** = useful for self-supervised pretraining, **FT** = useful for supervised fine-tuning on a target state, **BM** = benchmark/evaluation only. "Muse-mappable" refers to the electrode-mapping inferences explained in the first key question.

## Muse-specific datasets (MindBigData, Kaggle/Zenodo/OpenNeuro/NEMAR, Muse emotion data, Muse S Athena 2025–2026 releases)

### Takeaway
The best Muse-native resources are NEMAR **nm000287** (Muse S, 203 participants, about 158 h, sleep onset, CC-BY-NC-SA), **EKM-ED** (Muse S emotion, 47 participants, CC BY 4.0), and **MindBigData MU** (Muse 1, about 163k 2-second epochs, good for pretraining but the license is unclear). Most other Muse sets are tiny (4 to 26 people). I found **no public Muse S Athena dataset that includes fNIRS/optics**.

### Cited Findings
**NEMAR nm000287 – "Muse Sleep-Onset EEG" (EEG/EMG Foundation Challenge 2026, Track 03).** This is the most relevant Muse-native corpus I found.
- Device and size: a Muse S-family headset, 4 channels (TP9, AF7, AF8, TP10) stored at 128 Hz (the original may have been 256 Hz, unverified). It has 540 at-home recordings from 203 participants, about 157.5 h in total, each 6 to 30 min. — [nemarDatasets/nm000287](https://github.com/nemarDatasets/nm000287)
- Labels: one annotation per recording marking the first N2 sleep epoch. There are no full hypnograms and no self-reports. — [nm000287](https://github.com/nemarDatasets/nm000287)
- License and access: CC-BY-NC-SA-4.0 (credit "Muse Team"), DOI 10.82901/nemar.nm000287, EEG-BIDS/BrainVision files readable with MNE-BIDS. — [nm000287](https://github.com/nemarDatasets/nm000287)
- Split: 500 training and 40 test recordings, and every test participant also appears in training. Recording length leaks the target, so it must be hidden from models. — [nm000287](https://github.com/nemarDatasets/nm000287)
- Challenge context: the task is to predict time until the first N2 epoch, scored with W-bMAE in seconds. A sealed, non-public Muse evaluation set also exists. — [Challenge tracks page](https://neural-interfaces26.github.io/tracks.html); [UCSD NINE post](https://nine.ucsd.edu/post/neurips-challenge-2026/)

**EKM-ED – EmoKey Moments Muse EEG Dataset (Univ. of Granada).** The best open Muse emotion dataset I found.
- Content: Muse S EEG from 47 participants watching film clips chosen to elicit baseline, anger, sadness, happiness, and fear. It includes key-moment timestamps and per-clip SAM self-assessment ratings. — [Zenodo 8431451](https://zenodo.org/records/8431451); [UGR record](https://produccioncientifica.ugr.es/documentos/668fc432b9e7c03b01bd6125?lang=eu)
- Format: raw data at 256 Hz, preprocessed data downsampled to 128 Hz, and a cleaned-signal folder. About 4.3 GB, CC BY 4.0 (per a secondary summary of the Zenodo page). — [Zenodo 8431451](https://zenodo.org/records/8431451)

**MindBigData "MNIST of Brain Digits" – MU (Muse 1) subset.**
- Content: about 163,250 two-second Muse 1 four-channel signals recorded while a subject viewed digits 0–9. One other source gives 163,932. — [MindBigData 2022 paper (arXiv 2212.14746)](https://arxiv.org/pdf/2212.14746); [dataportals.org entry](https://dataportals.org/portal/mindbigdata-the-mnist-of-brain-digits)
- Mirrors: there is an 80/20 split on Hugging Face (DavidVivancos). — [HF MindBigData2022](https://huggingface.co/datasets/DavidVivancos/MindBigData2022)
- License: not stated for the MU subset. The dataportals entry has a blank license field. The ODbL license I found belongs to a different MindBigData set (MNIST-2B, recorded on a 128-channel device), so it does not cover MU. — [dataportals.org](https://dataportals.org/portal/mindbigdata-the-mnist-of-brain-digits); [HF MNIST-2B README](https://huggingface.co/datasets/DavidVivancos/MindBigData2023_MNIST-2B/raw/main/README.md)
- MindBigData 2022 also includes Muse 2 raw EEG (TP9/AF7/AF8/TP10) in its file format. — [arXiv 2212.14746](https://arxiv.org/pdf/2212.14746)

**Mendeley "EEG Recordings Capturing Student Stress Responses During Exams".**
- Content: Muse 2 recordings from 26 students (19 female, 7 male) taken during real exams, in raw and processed form with band powers. — [Mendeley Data fyj9by2t22](https://data.mendeley.com/datasets/fyj9by2t22/1)
- Labels and license: no stress labels or self-reports. CC BY 4.0, published 28 Apr 2025. — [Mendeley Data](https://data.mendeley.com/datasets/fyj9by2t22/1)

**Kaggle "EEG brainwave dataset: mental state" (Bird et al., birdy654).**
- Content: Muse TP9/AF7/AF8/TP10 recordings from 4 people (2 male, 2 female), 60 s each of relaxed, concentrating, and neutral states. Shared as extracted statistical features, not raw EEG. — [Kaggle](https://www.kaggle.com/datasets/birdy654/eeg-brainwave-dataset-mental-state)
- It is used as a 3-class benchmark in a 2026 EEG foundation-model paper (BrainCodes). — [BrainCodes arXiv 2610.29320](https://arxiv.org/pdf/2610.29320)

**Smaller Muse sets.**
- GitHub "yueeyue/Muse2-eeg": Muse 2 raw RAW_TP9/AF7/AF8/TP10 CSVs from 8 volunteers doing 6 activities, hosted on Dropbox. No clear license or DOI. — [GitHub](https://github.com/yueeyue/Muse2-eeg)
- Zenodo "EEG and Motion Signals Pilot Dataset": Muse S (Mind Monitor CSV) with raw EEG, band powers, accelerometer, gyroscope, and contact quality. Only about 67 s of data, CC BY 4.0, published 25 Aug 2026. Useful only as a file-format and parser test fixture. — [Zenodo 22093536](https://zenodo.org/records/22093536)
- Kaggle "EEG Muse2 Motor imagery". — [Kaggle](https://www.kaggle.com/datasets/muhammadatefelkaffas/eeg-muse2-motor-imagery-brain-electrical-activity)

**Muse data that is not openly released.**
- A 2026 flow-state study recorded 45 people playing adaptive Tetris on Muse-S and Emotiv Insight. The arXiv page gives no data release or data-availability link. — [arXiv 2609.19737](https://arxiv.org/abs/2609.19737)

**Muse S Athena device and vendor data.**
- Athena launched in March 2025 as a consumer EEG + fNIRS headband: 4 dry EEG channels at 256 Hz and a 5-optode fNIRS sensor at 64 Hz. — [FITT press release](https://insider.fitt.co/press-release/introducing-muse-s-athena-next-evolution-in-cognitive-fitness/); [Muse product page](https://choosemuse.com/products/muse-s-athena)
- Muse says it holds about "1 billion minutes" of data. That is a proprietary vendor claim, not a public dataset. — [Yahoo Finance/press](https://finance.yahoo.com/news/muse-ai-platform-delivers-clinical-110000046.html)

### Inferences
**Mapping Muse electrodes to standard caps (applies to every section).**
- Muse AF7 and AF8 are 10-10 positions, so any 10-10 cap that records AF7/AF8 maps directly.
- For 10-20 caps, the nearest substitutes for AF7/AF8 are Fp1/Fp2 (medial) and F7/F8 (lateral). For 32-channel 10-20 caps, a reasonable proxy is Fp1/Fp2 or an average of Fp1+F7 and Fp2+F8.
- TP9 and TP10 sit over the mastoid region behind the ear. Nearest substitutes are TP7/TP8, T7/T8, P7/P8, or mastoid/earlobe references (M1/M2, A1/A2).
- Re-referencing matters: Muse references to Fpz, while many lab datasets use linked mastoids/earlobes or CMS/DRL. A mastoid-referenced dataset effectively loses the TP9/TP10 information. These are my inferences, not sourced.

**What to use each Muse dataset for.**
- nm000287 is the only large Muse corpus (203 participants, about 158 h). It is the best domain-matched pretraining source and the best drowsiness/sleep-onset fine-tuning source.
- Its NC-SA license rules out commercial use and forces share-alike on derived data.
- Its 128 Hz storage rate limits learning above 64 Hz (gamma, EMG). Resample Athena's 256 Hz data to match, or train at 128 Hz.

**EKM-ED** is the only Muse dataset with self-reports (SAM ratings). Use it for fine-tuning and for benchmarking valence/arousal against self-reports.

**MindBigData MU** is good for domain-matched masked-reconstruction or contrastive pretraining despite its Muse 1 hardware and older firmware. Confirm the license before redistributing any derived weights.

**No public Athena optics data:** fNIRS/PPG pretraining must come from lab fNIRS datasets (see the fNIRS section) plus the user's own recordings.

### Gaps
- No public Muse S Athena dataset with fNIRS/PPG/optics was found on Zenodo, OpenNeuro, Kaggle, HF, or NEMAR in these searches.
- I could not verify the MindBigData MU license on mindbigdata.com.
- Several Muse datasets I know of were not verified this session, so I am not listing them as facts:
  - the Kaggle Bird et al. "feeling emotions" Muse set
  - Muse meditation datasets
  - Hashemi et al. Muse validation data
- I did not search Kaggle exhaustively; many small Muse uploads exist there with unclear provenance and licensing.
- A dataset of 28 participants with Muse and the Perceived Stress Scale (music listening) is mentioned in search summaries ([arXiv 2502.18835](https://arxiv.org/pdf/2502.18835)), but I did not confirm whether its data is public.

## Affective/emotion and stress datasets (DEAP, DREAMER, SEED, AMIGOS, WESAD, SAM40, mental arithmetic)

### Takeaway
The classic affect datasets are mostly behind EULAs (DEAP, SEED, AMIGOS, DREAMER) and use either wet 32–62-channel caps (Muse-mappable via Fp1/Fp2/F7/F8/T7/T8) or Emotiv 14-channel headsets (which include AF3/AF4, F7/F8, T7/T8 but no mastoid). WESAD is the standard multimodal stress benchmark but has no EEG and is non-commercial. PhysioNet EEGMAT (mental arithmetic) is the cleanest openly licensed stress/workload EEG set (ODC-By).

### Cited Findings
**DEAP.**
- 32-channel BioSemi ActiveTwo EEG. — [Evaluation in EEG emotion recognition review, arXiv 2505.18175](https://arxiv.org/pdf/2505.18175)
- The access terms could not be retrieved: the official QMUL page failed with an SSL error.

**DREAMER.**
- Emotiv EPOC, 14 channels. Access is restricted through a Zenodo request: you state your name, institution, position, and reason. — [Zenodo 546113](https://zenodo.org/records/546113); [HF MONSTER DREAMER README](https://huggingface.co/datasets/monster-monash/DREAMERV/blob/main/README.md)

**AMIGOS.**
- Emotiv EPOC, 14 dry channels at 128 Hz. — [arXiv 2505.18175](https://arxiv.org/pdf/2505.18175)

**SEED.**
- 62-channel 10-20 cap. — [arXiv 2505.18175](https://arxiv.org/pdf/2505.18175)

**WESAD.**
- Content: 15 lab participants. Signals are BVP, ECG, EDA, EMG, respiration, temperature, and 3-axis acceleration from a chest device and a wrist device. Conditions are neutral, stress, and amusement, plus questionnaires. 2.5 GB. — [Uni Siegen WESAD page](https://ubi29.informatik.uni-siegen.de/usi/data_wesad.html)
- License: the official page allows "scientific, non-commercial purposes" with credit. — [Uni Siegen](https://ubi29.informatik.uni-siegen.de/usi/data_wesad.html)
- Kaggle and Figshare mirrors list CC BY 4.0, which conflicts with the official page. Treat the dataset as non-commercial. — [Figshare mirror](https://figshare.com/articles/dataset/WESAD_Dataset/28830173); [chatppg summary](https://chatppg.com/research/datasets/wesad)
- About 80% of wearable-stress studies (n=67) in one review used WESAD, despite its 15 subjects. — [search summary via ResearchGate review](https://www.researchgate.net/publication/329116315_Wearable_affect_and_stress_recognition_A_review) (secondary)

**SAM40.**
- 40 subjects (14 female, 26 male), 32-channel Emotiv Epoc Flex gel kit. Tasks are Stroop, arithmetic, mirror-image recognition, and relaxation. Published in Data in Brief (DOI 10.1016/j.dib.2021.107772). — [PMC8749216](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8749216/)
- The hosting location (figshare) and license were not verified.

**PhysioNet EEGMAT – EEG during mental arithmetic.**
- 36 subjects, 23-channel 10/20 EEG referenced to linked ears. Each subject has a rest recording and a serial-subtraction recording, plus a count-quality group label. License: Open Data Commons Attribution v1.0. — [PhysioNet eegmat](https://physionet.org/content/eegmat/1.0.0/)

### Inferences
- **For a personal non-commercial app**, the open choices are EEGMAT (stress/arithmetic vs. rest, ODC-By) and EKM-ED (Muse emotion, CC BY). DEAP, SEED, AMIGOS, and DREAMER need signed EULAs and are typically academic-only, so they are best as **BM/FT** within research, not for shipping weights.
- **Emotiv 14-channel datasets** (DREAMER, AMIGOS, STEW) offer AF3/AF4, F7/F8, and T7/T8, a reasonable Muse proxy, but they are dry/saline at 128 Hz like Muse, which helps with domain matching.
- **WESAD** is relevant only for the PPG/HRV branch (wrist BVP is a proxy for forehead PPG) and for stress label definitions. It contains no EEG.

### Gaps
- DEAP, SEED (and SEED-IV/V/VII), and AMIGOS license texts were not retrieved. Based on prior knowledge they require signed academic EULAs, but this is unverified in this session.
- The SAM40 license and host were not verified.
- PPG-DaLiA license not verified.
- MAT, the Muse-recorded "mental arithmetic" dataset family, was not found.

## Mind-wandering, attention, and workload datasets (STEW, Shin 2018 EEG-fNIRS, Tufts fNIRS2MW)

### Takeaway
There are now several open datasets with experience-sampling thought probes (OpenNeuro ds007216 CC0, ds001787 meditation mind-wandering probes, ds004148, ds007629 ROAMM). Combined with workload sets (STEW, Shin 2018 n-back, Tufts fNIRS2MW CC BY 4.0), these give a credible route to focus vs. mind-wandering fine-tuning, though all are lab-grade caps, not Muse.

### Cited Findings
**OpenNeuro ds007216 (Kucyi et al.) – EEG-fMRI with online experience sampling.**
- 24 healthy adults (18–35). Tasks are the gradCPT and rest with intermittent experience sampling over 13 thought dimensions, plus mental health surveys. CC0 per the v1.1.0 record (per search summary). — [OpenNeuro ds007216](https://openneuro.org/datasets/ds007216/versions/1.1.0); [bioRxiv](https://www.biorxiv.org/content/10.64898/2026.02.04.703882v2.full)

**OpenNeuro ds001787 – "EEG meditation study".**
- 24 subjects, interrupted about every 2 minutes during meditation to rate concentration and mind-wandering. — [OpenNeuro ds001787](https://openneuro.org/datasets/ds001787/versions/1.1.0); [GitHub mirror](https://github.com/OpenNeuroDatasets/ds001787)
- Related analysis: alpha–theta dynamics during mind-wandering in breath-focus meditation, using experience sampling. — [bioRxiv 2020.10.23.351759](https://www.biorxiv.org/content/10.1101/2020.10.23.351759.full.pdf)

**OpenNeuro ds004148 – test-retest resting and cognitive-state EEG.**
- 60 participants × 3 sessions, with mind-wandering, sleep, emotion, and mental-health measures. — [OpenNeuro ds004148](https://openneuro.org/datasets/ds004148/versions/1.0.1); [PMC9470564](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9470564/)

**OpenNeuro ds007629 – ROAMM.**
- EEG plus eye-tracking during naturalistic reading, with span-level mind-wandering annotations from the "ReMind" retrospective self-report. — [OpenNeuro ds007629](https://openneuro.org/datasets/ds007629/versions/1.3.0)

**STEW – Simultaneous Task EEG Workload (IEEE DataPort).**
- 48 subjects doing the SIMKAP multitask, plus rest. Emotiv EPOC, 14 channels at 128 Hz, 2.5 min per condition, self-rated workload 1–9 (missing for subjects 5, 24, 42). A free IEEE account is needed. — [IEEE DataPort STEW](https://ieee-dataport.org/open-access/stew-simultaneous-task-eeg-workload-dataset)

**Shin et al. 2018 – simultaneous EEG + NIRS during cognitive tasks (TU Berlin).**
- 26 participants. The n-back task uses 3 sessions × 3 series of 0/2/3-back. — [Sci Data 2018](https://www.nature.com/articles/sdata20183)
- License conflict: Sci Data metadata lists CC0; a ResearchGate copy shows CC BY 4.0; individual DepositOnce files are labeled CC BY or CC0. Check each download. — [DepositOnce](https://depositonce.tu-berlin.de/items/version/25)
- Code is MIT-licensed. — [GitHub JaeyoungShin/simultaneous_EEG-NIRS](https://github.com/JaeyoungShin/simultaneous_EEG-NIRS)

**Tufts fNIRS2MW.**
- n-back (0–3) fNIRS from 68 recommended participants (87 total), about 21 min each, in 30 s windows. Dataset CC BY 4.0, code MIT. NeurIPS 2021 Datasets & Benchmarks. — [Tufts fNIRS2MW page](https://tufts-hci-lab.github.io/code_and_datasets/fNIRS2MW.html); [NeurIPS paper](https://datasets-benchmarks-proceedings.neurips.cc/paper_files/paper/2021/file/bd686fd640be98efaae0091fa301e613-Paper-round2.pdf)
- An audio n-back companion set (NIRS-X) has 53 users. — [NIRS-X](https://tufts-hci-lab.github.io/code_and_datasets/NIRS-X.html)

### Inferences
**Focus vs. mind-wandering.**
- ds001787 is the most on-target dataset: meditation with thought probes matches the app's "meditation + mind-wandering" use case.
- ds007216 (gradCPT + 13-dimension experience sampling, CC0) is the best template for how to design self-report probes in the app.
- Both use lab caps. Map them to Muse channels (Fp1/Fp2/F7/F8 for AF7/AF8; T7/T8/TP7/TP8 for TP9/TP10) before fine-tuning.

**Workload/effort.**
- fNIRS2MW is the strongest prefrontal-fNIRS fine-tuning and benchmark set for Athena's optics. It uses a forehead fNIRS band, so its sensor geometry is close to Athena's.
- Shin 2018 is the only well-known set with simultaneous EEG and fNIRS on the same n-back task. It is ideal for multimodal fusion pretraining.

### Gaps
- I did not verify the ds001787 license, channel count, or EEG system (the OpenNeuro page did not render), nor the licenses for ds004148 and ds007629.
- Not searched: SART/gradCPT EEG attention datasets beyond these, and the "Mental Attention State Detection" Kaggle set (believed to be Emotiv, unverified).

## fNIRS (prefrontal) and PPG/HRV open datasets

### Takeaway
The October–November 2026 fNIRS foundation-model corpus (67 public datasets, 2,798 participants, 1,955 h, dataloaders on GitHub) is the single best starting point for pretraining Athena's optical branch. Prefrontal workload sets (fNIRS2MW, Shin 2018) are the best for fine-tuning. For PPG/HRV, WESAD (wrist BVP) and K-EmoPhone (in-the-wild) are the relevant labeled sources, both with access restrictions.

### Cited Findings
**fNIRS foundation-model corpus.**
- Posso-Murillo, arXiv 2610.40277 (v1 29 Oct 2026, v3 5 Nov 2026): 67 public fNIRS datasets, 2,798 participants, 1,955 h, HbO/HbR with MNI channel positions. Dataloaders and preprocessing are at github.com/sposso/fnirs-datasets. Per-dataset licenses are not specified on the abstract page. — [arXiv 2610.40277](https://arxiv.org/abs/2610.40277); [GitHub sposso/fnirs-datasets](https://github.com/sposso/fnirs-datasets)

**Prefrontal fNIRS fine-tuning sets.**
- fNIRS2MW (CC BY 4.0) and Shin 2018 EEG+NIRS: see the mind-wandering/workload section. — [Tufts](https://tufts-hci-lab.github.io/code_and_datasets/fNIRS2MW.html); [Sci Data](https://www.nature.com/articles/sdata20183)
- An HF mirror of fNIRS data exists (pkr7098/fNIRS); provenance not checked. — [HF pkr7098/fNIRS](https://huggingface.co/datasets/pkr7098/fNIRS)

**PPG/HRV.**
- WESAD provides wrist BVP (PPG) plus ECG and EDA under stress, amusement, and neutral conditions; non-commercial. — [Uni Siegen](https://ubi29.informatik.uni-siegen.de/usi/data_wesad.html)

### Inferences
**Athena optics vs. lab fNIRS.**
- Athena's raw optics at 64 Hz carry both a hemodynamic (fNIRS) signal and a cardiac (PPG) signal. Lab fNIRS datasets typically sample at 7–50 Hz, so pulse information may be aliased or absent.
- Pretrain the hemodynamic encoder on the fNIRS corpus filtered to below about 0.5 Hz.
- Pretrain the PPG/HRV encoder separately on PPG datasets.
- These are inferences, not sourced.

**Commercial use.** The fNIRS corpus licenses will vary per dataset; the corpus paper says nothing on this, so filter by license before any non-research use.

### Gaps
- Not verified: PPG-DaLiA, BUT-PPG, MIMIC PPG, or forehead-PPG-specific datasets. I found no forehead-PPG open dataset in this session.
- I did not obtain a list of which of the 67 fNIRS datasets are prefrontal-only.

## Depression, rumination, anxiety, and craving EEG datasets (MODMA, PRED+CT, OpenNeuro)

### Takeaway
MODMA is the most Muse-like depression dataset: it includes a 3-electrode wearable forehead EEG on 55 subjects, but access requires a signed EULA. PRED+CT/OpenNeuro ds003478 gives 64-channel resting EEG on 122 students with BDI scores. I found no openly hosted craving/cue-reactivity EEG dataset.

### Cited Findings
**MODMA (Lanzhou University).**
- Has 128-electrode and 3-electrode wearable resting EEG. The 3-electrode set covers 55 subjects: 26 depressed outpatients and 29 controls. — [MODMA arXiv 2002.09283](https://arxiv.org/abs/2002.09283v3); [PMC9018722](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9018722/)
- Access: download, sign, and scan a EULA, upload it, then wait for admin approval (days). — [MODMA application page](https://modma.lzu.edu.cn/data/application/)
- A mirror exists at the UK Data Service. — [UKDS ReShare 854301](https://reshare.ukdataservice.ac.uk/854301)
- Related work: "Depression Detection using Resting State Three-channel EEG Signal" (arXiv 2002.09175), listed on the MODMA site. — [MODMA](https://modma.lzu.edu.cn/)

**PRED+CT / OpenNeuro ds003478.**
- Resting 64-channel EEG plus clinical data from 122 college students. Groups: high BDI (>13, N=46) and controls (<7, N=75). — [Preprints 202407.2337](https://www.preprints.org/manuscript/202407.2337); [PRED+CT paper, Front. Neuroinform. 2017](https://doi.org/10.3389/fninf.2017.00067); [predict.cs.unm.edu](https://predict.cs.unm.edu/)

**Craving/cue-reactivity.**
- The closest public dataset found is the Bu et al. 2021 Frontiers nicotine neurofeedback/smoking cue-reactivity EEG dataset; its hosting location was not stated. — [Frontiers 10.3389/fnins.2021.647844](https://www.frontiersin.org/articles/10.3389/fnins.2021.647844/pdf)
- Methamphetamine cue-craving EEG studies report no public release. — [PMC10210338](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10210338/); [PMC9114476](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9114476/)

**Mental health covariates.**
- HBN-EEG (see the pretraining section) carries psychopathology scores. The NeurIPS 2025 challenge predicted four psychopathology factors from it. — [EEG Foundation Challenge paper](https://www.researchgate.net/publication/392980696_EEG_Foundation_Challenge_From_Cross-Task_to_Cross-Subject_EEG_Decoding)

### Inferences
- **MODMA 3-channel** is the strongest fine-tuning and benchmark source for a forehead "negative mood" probe. Confirm its exact electrode sites; the Fp1/Fpz/Fp2 placement is not verified.
- **Rumination and negative mood** in healthy users are better approximated by BDI/trait data (ds003478) or the mental-health surveys in ds007216 and ds004148 than by clinical MDD datasets.
- The app is non-medical, so these should calibrate trait-level features, not diagnose.
- **Craving** will likely require the user's own data with EMA labels.

### Gaps
- Not verified: the MODMA 3-channel electrode positions, MODMA's commercial-use terms, and the ds003478 license (OpenNeuro is typically CC0, but unverified here).
- No dedicated rumination-induction EEG dataset or anxiety EEG dataset was found or verified in this session.
- I found no public craving EEG dataset on OpenNeuro.

## Experience-sampling/EMA datasets combined with wearables

### Takeaway
No public dataset combines consumer EEG with EMA in the wild. K-EmoPhone (77 students × 7 days, smartphone + wristband + in-situ emotion/stress/attention ESM) is the best label-design template and PPG/HRV fine-tuning source, but it is restricted-access. For EEG+ESM, the lab datasets ds007216 and ds001787 are the closest.

### Cited Findings
**K-EmoPhone.**
- In-situ emotion, stress, and attention labels from smartphone + wearable over 1 week. Published in Scientific Data 2023. — [PMC10238385](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10238385/)
- Access: the Zenodo record is restricted. Request it after completing a user agreement; it is offered "primarily for academic research purposes," and the EULA was updated in v1.1.2 (June 2023). — [Zenodo 7606611](https://zenodo.org/records/7606611)
- Participant count: n=80 per the 2022 Zenodo text vs. 77 per the paper (discrepancy). — [Zenodo 6851298](https://zenodo.org/record/6851298)

**EmoPhone.**
- A newer multi-wave in-the-wild mobile/wearable affect dataset (arXiv 2609.16581, 2026). Details not verified. — [arXiv 2609.16581](https://arxiv.org/pdf/2609.16581)

**Consumer wearable + EMA field studies.**
- A PLoS ONE study (consumer HR/activity + 6 EMAs per day) found HR +8.9 bpm during exams. — [PLoS ONE](https://journals.plos.org/plosone/article/file?type=printable&id=10.1371%2Fjournal.pone.0229942)
- A study detected prolonged stress from wearable biosensors + EMA. — [PMC10623231](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10623231/)
- The data availability of both was not checked.

### Inferences
- The project will need its own EMA+Muse dataset for personal calibration.
- Public EMA datasets are useful for prompt design, label taxonomy (K-EmoPhone's emotion/stress/attention axes; ds007216's 13 thought dimensions), and for pretraining the PPG/HRV branch.

### Gaps
- Not searched: StudentLife, the Tesserae project, and LifeSnaps (Fitbit + EMA), so their access and licenses were not verified.

## Sleep and drowsiness EEG datasets (forehead/behind-ear relevant)

### Takeaway
For drowsiness and sleep onset, Muse nm000287 is the best domain match. Sleep-EDF (Fpz-Cz, ODC-By) gives frontal single-channel data with full hypnograms. Dreem DOD-H/DOD-O give multi-scored PSG with frontal and mastoid derivations, now on Zenodo.

### Cited Findings
**Muse nm000287.**
- First-N2 sleep-onset labels, 203 participants, CC-BY-NC-SA. — [nm000287](https://github.com/nemarDatasets/nm000287)

**Sleep-EDF Expanded (PhysioNet).**
- 197 overnight PSGs (153 Sleep Cassette, 44 Sleep Telemetry). EEG channels Fpz-Cz and Pz-Oz at 100 Hz, R&K hypnograms, ODC-By v1.0. — [PhysioNet sleep-edfx](https://physionet.org/content/sleep-edfx/1.0.0/)

**Dreem Open Datasets.**
- DOD-H: 25 healthy adults, 12 EEG derivations. DOD-O: 55 OSA patients, 8 derivations including F3/M2 and C3/M2, 250 Hz. Scored by multiple technicians. — [arXiv 1911.03221](https://arxiv.org/abs/1911.03221v2)
- Data on Zenodo; DOD-O has 56 files (exclude one record lacking consensus); the repository is MIT-licensed, but no data license is stated on GitHub. — [GitHub dreem-learning-open](https://github.com/Dreem-Organization/dreem-learning-open); [Zenodo 15900394](https://zenodo.org/records/15900394)

### Inferences
- **Sleep-EDF**: Fpz-Cz is close to Muse's Fpz reference and AF7/AF8, so it is a good proxy for frontal sleep/drowsiness features (100 Hz limits high-frequency content).
- **Dreem DOD**: mastoid-referenced frontal derivations (F3/M2, F4/M1) resemble an AF7–TP9 bipolar Muse derivation. Useful for **FT/BM** of drowsiness and sleep-stage heads.
- Check the Zenodo record's license before any commercial use.

### Gaps
- Not verified: the Dreem data license on Zenodo, SHHS/MESA (NSRR, DUA-gated), and driver-drowsiness EEG datasets (e.g., SEED-VIG).

## Large pretraining corpora (TUH EEG, HBN, aggregated corpora) and Muse channel mapping

### Takeaway
The most practical 2026 route is the EEGDash Corpus (77 redistributable datasets, 14,075 h, 7,272 subjects, per-dataset licenses kept, HF Zarr). Add HBN-EEG (CC-BY-SA 4.0 via NEMAR/OpenNeuro, with psychopathology labels), TUH EEG (largest clinical corpus, registration required), and domain-matched Muse data (nm000287, MindBigData MU). All 10-20 corpora contain Fp1/Fp2/F7/F8/T7/T8 for a Muse-like 4-channel subset, but the mastoid sites (TP9/TP10) are usually only proxied.

### Cited Findings
**EEGDash Corpus.**
- Shahi, Aristimunha, Delorme, arXiv 2611.06356 (v1 4 Nov 2026): 77 redistributable datasets from the REVE pretraining corpus at 200 Hz, 14,075 h, 7,272 subjects. "Every dataset keeps its licence." Distributed via EEGDash and a Hugging Face Zarr store ("eegdash-corpus-v0"). — [arXiv 2611.06356](https://arxiv.org/abs/2611.06356)

**HBN-EEG (Healthy Brain Network), OpenNeuro ds005505–ds005515 (Releases 1–11).**
- License: OpenNeuro pages describe CC BY-SA 4.0, but the Release 1 metadata shows CC0 (conflict). A separate non-commercial release (CC-BY-NC-SA-4.0) is not hosted on OpenNeuro. — [OpenNeuro ds005505](https://openneuro.org/datasets/ds005505/versions/1.0.1/download); [ds005512](https://openneuro.org/datasets/ds005512/versions/1.0.1)
- The challenge paper says the first 11 releases are freely available under CC-BY-SA-4.0 through NEMAR. — [EEG Foundation Challenge paper](https://www.researchgate.net/publication/392980696_EEG_Foundation_Challenge_From_Cross-Task_to_Cross-Subject_EEG_Decoding)

**TUH EEG Corpus.**
- Size: v0.6.0 had 16,986 sessions from 10,874 subjects; later descriptions say more than 30,000 records and more than 16,000 patients. — [PMC4865520](https://pmc.ncbi.nlm.nih.gov/articles/PMC4865520)
- The TUAB abnormal subset has 2,993 recordings of at least 15 min from 2,329 patients. — [arXiv 2002.05115](https://arxiv.org/pdf/2002.05115)
- Access is free with registration. — [PMC4865520](https://pmc.ncbi.nlm.nih.gov/articles/PMC4865520)

**EEG/EMG Foundation Challenge 2026 (NeurIPS).**
- Uses Muse sleep onset (Track 03) and PROTEUS BCI (41 channels at 500 Hz, mental subtraction/word generation/MI; nm000290) as training sources. Tracks launch pending provider approvals. — [Challenge site](https://neural-interfaces26.github.io/index.html); [Ethics page](https://neural-interfaces26.github.io/ethics.html); [NEMAR nm000290](https://nemar.org/dataset/nm000290)

### Inferences
**Pretraining recipe for this project:**
1. Self-supervised pretraining on a 4-channel virtual-Muse montage extracted from EEGDash, HBN, and TUH.
   - AF7/AF8: use them directly where present; otherwise Fp1/Fp2 or F7/F8.
   - TP9/TP10: T7/T8, TP7/TP8, or P7/P8, re-referenced to Fpz where possible.
2. Domain-adaptive pretraining on nm000287 and MindBigData MU (true Muse dry-electrode noise characteristics).
3. Fine-tuning on EKM-ED, ds001787/ds007216, EEGMAT/SAM40/STEW, MODMA-3ch, Sleep-EDF/DOD.
4. Personal calibration with the user's own EMA-labeled Athena sessions.

**Licensing for commercial use.** TUH (registration/DUA), the HBN non-commercial release, nm000287 (NC-SA), WESAD (non-commercial), and EULA datasets (DEAP/SEED/AMIGOS/DREAMER/MODMA/K-EmoPhone) all constrain commercial use of trained weights. For a strictly personal, non-commercial app they are usable, subject to each EULA's redistribution clauses.

### Gaps
- Not verified: the current TUH EEG total hours, the exact TUH DUA text, and whether the EEGDash corpus includes HBN/TUH or which of its datasets have NC licenses.
- REVE corpus details were not fetched.
- Not investigated: other foundation-model corpora (e.g., those used by LaBraM, CBraMod) and the BrainCodes paper's dataset list ([arXiv 2610.29320](https://arxiv.org/pdf/2610.29320)).
