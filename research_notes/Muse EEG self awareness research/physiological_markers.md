# Physiological Markers of Anxiety, Rumination, Craving and Mind-Wandering Measurable with a Few-Channel Consumer Headband (Muse S Athena: EEG TP9/AF7/AF8/TP10 @256 Hz, forehead optics fNIRS/PPG @64 Hz, IMU @52 Hz)

Notes on sourcing: Items marked "(abstract/snippet only)" were verified only from search abstracts or snippets, not full text. Items marked "(canonical; DOI from prior knowledge, not re-fetched this session)" are foundational papers whose details I am confident of but did not re-open in this session. The report writer should treat those as lower-verification. Several key 2026 meta-analyses were paywalled (HTTP 403), so their numbers are from abstracts.

---

## 1. Anxiety / acute stress: EEG, HRV and fNIRS markers of state anxiety in real time; consumer-device validation

### Takeaway
HRV is the best-replicated marker. Reduced vagally mediated HRV (HF power, RMSSD) is reliably linked to anxiety, but the effects are small (g ≈ −0.29 between people), so it works far better as a change from a person's own baseline than as an absolute threshold. EEG stress and anxiety classifiers built on Muse report 78–93% accuracy, but they come from small samples (n ≈ 28–65), use questionnaire labels and are cross-validated within one study. None has been independently replicated. Wearable prefrontal fNIRS has no meta-analytic support for real-time state anxiety detection.

### Cited Findings
**HRV**
- Chalmers et al. (2014) meta-analysis: 36 articles, 2,086 people with anxiety disorders vs 2,294 controls. Anxiety disorders showed lower HRV, HF Hedges' g = −0.29 (95% CI likely −0.41 to −0.17, p < .001). Panic disorder (n=447), PTSD (n=192), GAD (n=68) and social anxiety (n=90) showed HF reductions; OCD (n=40) did not. The authors call it a "small-to-moderate" effect. This is a trait/group-level finding. — [Chalmers et al. 2014, Front Psychiatry (PMC4092363)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4092363/)
- Stress and HRV meta-analysis/review: acute stress is typically marked by lower parasympathetic indices (HF, RMSSD) and a higher LF or LF/HF ratio (canonical; DOI from prior knowledge, not re-fetched this session). — [Kim et al. 2018, Psychiatry Investigation](https://doi.org/10.30773/pi.2017.08.17)
- A 2026 review of physiological stress detection warns that HRV's "reliability in wearable, real-world settings should be interpreted cautiously" and recommends artifact handling and/or multimodal fusion. — [MDPI Sensors 2026 review](https://www.mdpi.com/1424-8220/26/5/1616)

**EEG (frontal midline theta, alpha, band powers)**
- Frontal midline theta (FMθ, ~4–8 Hz, Fz/FCz, generated in mid-cingulate/medial PFC) is meta-analytically linked to anxiety and to the need for cognitive control (canonical; DOI from prior knowledge, not re-fetched). — [Cavanagh & Shackman 2015, J Physiol Paris](https://doi.org/10.1016/j.jphysparis.2014.04.003)
- Muse perceived-stress classification: 28 participants recorded with the 4-channel Muse in two phases, labeled with the Perceived Stress Scale. This measures perceived chronic stress, closer to a trait than a moment-to-moment state. The vendor blog cites 92.85% accuracy, but I could not confirm that figure in the paper. — [Arsalan et al. 2019, IEEE EMBC](https://ieeexplore.ieee.org/abstract/document/8753565/); [Muse blog](https://choosemuse.com/blogs/news/new-study-harnessing-eeg-based-brain-sensing-devices-for-stress-management-1)
- Muse multi-class anxiety detection from resting-state EEG: random forest, 87.69% (2-class) and 83.07% (3-class). Sources disagree on sample size (Muse blog says 65; the Springer abstract describes 28-participant data). The labels are questionnaire-based anxiety levels, so this is group/trait classification, not real-time state detection. — [J Ambient Intell Humaniz Comput 2021](https://link.springer.com/article/10.1007/s12652-021-03249-y); [Muse blog](https://choosemuse.com/blogs/news/detecting-multi-class-anxiety-with-eeg-technology)
- LSTM stress classification on Muse EEG from 35 volunteers (abstract/snippet only). — [PMC9071939](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9071939/)
- Multimodal perceived-stress framework using wearable physiological sensors including EEG (arXiv; abstract/snippet only). — [arXiv 2206.10846](https://arxiv.org/pdf/2206.10846)

**fNIRS (prefrontal HbO)**
- Large-sample fNIRS study (>800 people, Depression and Anxiety 2026): more severe anxiety was associated with lower prefrontal oxy-Hb. The authors state diagnostic utility was not evaluated. This is a trait/group finding. — [Ren et al. 2026, Depression and Anxiety](https://onlinelibrary.wiley.com/doi/10.1155/da/9910013)
- Resting-state fNIRS functional connectivity plus machine learning predicted individual state anxiety (not trait anxiety). This used a research multichannel system and connectivity features, not a single forehead channel. — [Translational Psychiatry 2020](https://www.nature.com/articles/s41398-020-01088-7)
- 2026 Frontiers study: a resting-state fNIRS HbO classifier separated emerging adults with elevated anxiety from controls. The authors frame the DLPFC HbO features as "candidate biomarkers that merit further investigation." — [Front Psychiatry 2026](https://www.frontiersin.org/journals/psychiatry/articles/10.3389/fpsyt.2026.1722529/pdf)

**Consumer-device validation**
- Muse vs BioSemi (research-grade) for spectral measures and frontal alpha asymmetry (FAA): the study compared mastoid-referenced Muse data with BioSemi. Only the abstract was accessible; full results not verified. — [ResearchGate: Validating the wearable MUSE headset for EEG spectral analysis and FAA](https://www.researchgate.net/publication/357850452_Validating_the_wearable_MUSE_headset_for_EEG_spectral_analysis_and_Frontal_Alpha_Asymmetry)
- A 2025 comparison of consumer headbands against a research amplifier found Muse had "the poorest signal quality, with extremely low alignment" with the reference. The authors attribute this partly to flat silver-ink electrodes. — [PMC11679099, Comparison of EEG spectral characteristics, consumer vs research-grade](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11679099/)

### Inferences
- For a personal tool, the most defensible "stress/anxiety arousal" signal is a within-person drop in RMSSD/HF together with a rise in heart rate relative to a rolling personal baseline, with motion artifacts removed using the IMU. The between-person effect (g ≈ −0.3) is too small for absolute thresholds.
- Published Muse anxiety/stress accuracies (78–93%) are likely inflated by small n, questionnaire labels and possible window-level leakage in cross-validation. They should not be quoted to users as detection accuracy.
- FMθ is a plausible anxiety/cognitive-control marker, but Muse has no Fz/FCz electrode. AF7/AF8 pick up only a lateralized, attenuated version, and frontal theta at AF7/AF8 overlaps strongly with eye-movement and blink artifacts. FMθ is therefore not feasible to measure cleanly on Muse.
- Muse's "fNIRS" is a single forehead optical site per side. Short-separation regression for scalp blood flow may be impossible or limited, and forehead HbO is heavily confounded by systemic, skin-level blood flow changes that track HR and arousal. Expect it to add little independent information beyond PPG.

### Gaps
- No validation studies were found for Mendi (fNIRS headband), Emotiv or OpenBCI on state-anxiety detection. No peer-reviewed Muse S Athena fNIRS validation was found.
- No study was found testing Muse EEG for moment-to-moment state anxiety, such as an anxiety induction with leave-subject-out or prospective validation.
- The exact sample size and accuracy of the Muse multi-class anxiety paper need checking against full text (28 vs 65 participants).
- Theta/beta ratio as an anxiety marker (e.g., attentional control in trait anxiety) was not searched in this session.

---

## 2. Depressive rumination / repetitive negative thinking (RNT): FAA and its replication problems, DMN-related markers, EEG of rumination episodes, HRV

### Takeaway
FAA, the classic "depression marker," failed meta-analytic and multiverse replication. It should not be used as a rumination or depression indicator. State rumination has a few small EEG studies (alpha and beta changes; one 2024 medRxiv decoding study) but no replicated scalp signature. The most robust within-person physiological correlate of rumination or worry is a modest drop in vagally mediated HRV during perseverative cognition compared with the person's own baseline.

### Cited Findings
**Frontal alpha asymmetry: replication failure**
- Van der Vinne et al. (2017) meta-analysis: 16 studies, MDD n=1,883 vs controls n=2,161. After heterogeneity was resolved, the grand mean effect size was d = −0.007 (95% CI −0.090 to 0.075). The authors conclude FAA has "limited diagnostic value" in MDD, and larger studies were less likely to report large effects. — [van der Vinne et al. 2017, NeuroImage: Clinical (Semantic Scholar)](https://www.semanticscholar.org/paper/Frontal-alpha-asymmetry-as-a-diagnostic-marker-in-A-Vinne-Vollebregt/22a0a94b8b91e42acfcf8ce3925d62164c1deb6d); [Maastricht record](https://cris.maastrichtuniversity.nl/en/publications/frontal-alpha-asymmetry-as-a-diagnostic-marker-in-depression-fact/)
- Kołodziej et al. (eLife 2021) multiverse analysis: five independent datasets, 388 participants, 270 analysis pipelines. FAA did not replicate as a depression indicator, and Bayes factors gave moderate evidence for the null. — [eLife 2021](https://elifesciences.org/articles/60595); [bioRxiv preprint](https://www.biorxiv.org/content/10.1101/2020.06.30.180760v1.full)
- Large-scale short-term reliability study on several EEG systems: parietal rightward alpha asymmetry replicated, but the expected overall frontal asymmetry did not. — [Brain Structure & Function 2021](https://link.springer.com/article/10.1007/s00429-021-02399-1)
- Older meta-analysis reporting a moderate FAA–depression association, which later, larger work did not support (canonical; DOI from prior knowledge, not re-fetched). — [Thibodeau, Jorgensen & Kim 2006, J Abnorm Psychol](https://doi.org/10.1037/0021-843X.115.4.715)
- 2025 medRxiv systematic review/meta-analysis of resting EEG in depression: describes FAA findings as "inconclusive," reflecting specificity problems and methodological heterogeneity (preprint, not peer-reviewed). — [medRxiv 2025.10.22.25338525](https://www.medrxiv.org/content/10.1101/2025.10.22.25338525v1.full.pdf)

**EEG during rumination episodes (state-level)**
- Rumination-induction EEG with source localization: high vs low trait ruminators. Ruminators showed lower alpha power in an anterior cingulate cluster across all conditions (a group effect, i.e. trait-like, not specific to the induction). — [Cognitive, Affective & Behavioral Neuroscience 2016 (PMC5153413)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5153413/)
- "Decoding ruminative states from neurophysiological patterns" (medRxiv 2024, 64-channel EEG): multivariate alpha/beta/theta power and connectivity to separate induced rumination from distraction. Reports higher left-temporal beta during state rumination vs positive/neutral conditions, and increased frontal-midline theta (abstract/snippet only; full text blocked, so accuracy figures unverified; preprint). — [medRxiv 2024.05.15.24307414](https://www.medrxiv.org/content/10.1101/2024.05.15.24307414v1.full.pdf)
- Anger-rumination dissertation: alpha and theta changes during rumination vs neutral were "slight." The author suggests alpha may index negative mood generally rather than rumination specifically. — [University of Southern Mississippi dissertation](https://aquila.usm.edu/cgi/viewcontent.cgi?article=3556&context=dissertations)
- Effective-connectivity work across four EEG experiments on induced RNT (clinical and non-clinical) in theta/alpha/beta (abstract/snippet only). — [ResearchGate: The vicious cycle of rumination](https://www.researchgate.net/publication/366186989_The_vicious_cycle_of_rumination_Effective_connectivity_study_of_Repetitive_Negative_Thinking_in_clinical_and_non-clinical_groups)
- Neuroimaging meta-analysis of perseverative cognition (fMRI; DMN and related regions). This is not measurable with scalp EEG at 4 channels, but it supports the view that rumination engages medial/default-mode systems (abstract/snippet only). — [Psychiatry Research: Neuroimaging 2019](https://www.sciencedirect.com/science/article/abs/pii/S0925492719302471)

**HRV and rumination/worry (perseverative cognition)**
- Ottaviani et al. (2016) meta-analysis: perseverative cognition (worry + rumination) was associated with lower HRV, g = .15 in experimental studies and g = .27 in correlational studies. Moderators included state vs trait measures, worry vs rumination, induction type and study quality. Worry and rumination reduced vmHRV by a similar amount. — [Ottaviani et al. 2016, Psychol Bull (ResearchGate)](https://www.researchgate.net/publication/287797481_Physiological_Concomitants_of_Perseverative_Cognition_A_Systematic_Review_and_Meta-Analysis); [DOI 10.1037/bul0000036](https://scholar.google.com/scholar_lookup?doi=10.1037/bul0000036&amp=&pmid=26689087)
- Newer series of lab meta-analyses (2026 Int J Psychophysiol / OSF preprint): between-subject effects (resting) were non-significant, with significant heterogeneity not explained by moderators. Within-subject vmHRV reliably decreased during perseverative-cognition inductions relative to resting baseline. Recovery analyses were dominated by rumination studies. No publication bias was detected (abstract/snippet only; full text 403). — [ScienceDirect 2026](https://www.sciencedirect.com/science/article/abs/pii/S0167876026000516); [Authorea preprint](https://www.authorea.com/doi/full/10.22541/au.172462103.32153806/v1); [Sciety/OSF](https://sciety.org/articles/activity/10.31234/osf.io/w9dbn_v1)
- Field study: work-related rumination was associated with HRV in daily life. — [PMC5281594](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5281594/)
- Resting HRV relates differently to facets of rumination (brooding vs reflection) and to trait anxiety. — [Frontiers 2017 (PMC5671536)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5671536/)

### Inferences
- The evidence points the product toward within-person HRV deviations during self-reported "stuck thought" episodes, not toward trait markers such as FAA. Even then, an HRV drop is not specific to rumination; it also occurs with physical or mental effort, posture changes and speech. It can prompt reflection but cannot identify rumination.
- FAA from AF7/AF8 is technically computable on Muse, but given the null meta-analytic results for depression and the absence of rumination-specific evidence, presenting it as a "negative thinking" index would be scientifically unjustified.
- The medRxiv left-temporal beta finding is intriguing because TP9 sits near the left temporal area. However, temporal beta at TP9 is the band most contaminated by temporalis/jaw EMG, so any "rumination beta" at TP9 must be ruled out as muscle tension, which itself co-occurs with negative affect.

### Gaps
- No study was found using Muse or any consumer EEG to detect rumination episodes.
- No full-text accuracy for the 2024 rumination decoding preprint (403 blocked); no replication found.
- No fNIRS evidence specific to state rumination was found in this session.

---

## 3. Craving / addictive urges: EEG cue-reactivity markers, HRV during craving; smoking, alcohol, gambling, phone/social media

### Takeaway
The robust cue-reactivity markers are ERPs (P300 and especially the LPP), which need time-locked stimulus presentation. That is feasible in a structured Muse "cue task" (Krigolson showed Muse can capture P300), but not for passive, spontaneous everyday urges. Spectral and FAA markers of craving rest on small single studies. There is no credible evidence base for detecting phone or social-media urges physiologically.

### Cited Findings
- Littel et al. (2012) meta-analysis: substance users showed a medium effect of enhanced P300 to drug vs neutral pictures (SMD = 0.61). P300 reactivity was associated with subjective craving. — [Neurosci Biobehav Rev 2012](https://www.sciencedirect.com/science/article/abs/pii/S0149763412000735)
- 2026 pre-registered systematic review and meta-analysis of EEG cue reactivity (Part I: ERP): LPP to addiction cues was larger in people with addictive behaviors, Hedges' g ≈ 0.96 (14 studies). P300 showed only a small effect. Note: the abstract appears internally inconsistent on study counts (e.g., 5 P300 studies), so the numbers need full-text verification (403 blocked). — [Neurosci Biobehav Rev 2026](https://www.sciencedirect.com/science/article/pii/S0149763426001946)
- 2021 meta-analysis: stimulant and depressant use disorders showed enhanced drug-cue P300 relative to controls (abstract/snippet only). — [Int J Psychophysiol 2021](https://www.sciencedirect.com/science/article/abs/pii/S0167876021009041)
- Systematic review of P300 and self-reported craving in substance use disorders. — [ResearchGate 2023](https://www.researchgate.net/publication/374642069_Associations_of_the_P300_Event-Related_Potentials_and_Self-Reported_Craving_in_Substance_Use_Disorders_A_Systematic_Review)
- Smoking FAA: in smokers (n=22), frontal alpha asymmetry shifted toward left frontal hypoactivation during cigarette-cue exposure, particularly in women. This is a small, single study. — [Knott et al., Craving-induced EEG reactivity in smokers (PubMed 19212134)](https://pubmed.ncbi.nlm.nih.gov/19212134/)
- FAA framed as an approach-motivation index in cannabis use disorder (inhibitory control study). — [PMC6770848](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6770848/)
- Muse can capture ERPs: Krigolson et al. (2017), n=60. The N200 and P300 (oddball task) and the reward positivity (reward-learning task) were statistically confirmed with Muse, without event markers, by recording directly after each stimulus on a laptop. Because Muse lacks standard electrode positions, components were analyzed at non-standard sites. — [Krigolson et al. 2017, Front Neurosci (PMC5344886)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5344886/)

### Inferences
- A feasible craving feature is an app-controlled cue-reactivity probe: show personal cue images (cigarette, drink, app icon) interleaved with neutral images and measure P300/LPP-like positivity at TP9/TP10 (the closest posterior-ish sites) relative to neutral. That is an assessment session, not continuous monitoring. Single-trial ERP at 4 dry channels would be too noisy; dozens of trials averaged would be needed.
- Spontaneous urges in daily life have no time-locking event, so ERPs do not apply. FAA "approach motivation" is the only spectral candidate, and its evidence base is small-n and inherits FAA's reliability problems (see Section 2).
- HRV during craving is plausible as non-specific arousal, but this session found no meta-analytic HRV-craving evidence.

### Gaps
- HRV during craving (alcohol, smoking): no meta-analysis found in this session.
- Gambling and gaming cue reactivity: possibly included in the 2026 meta-analysis ("addictive behaviors"), but subgroup effects not verified.
- Phone/social-media urges: no physiological marker studies found. This should be treated as an evidence gap.
- Part II (spectral/oscillatory cue-reactivity) of the 2026 meta-analysis was not located.

---

## 4. Mind-wandering vs on-task: alpha, theta, P3 attenuation, blink rate; Muse studies; within-person accuracy

### Takeaway
This is the best-supported target for a few-channel headband. Several markers converge (alpha and theta changes, P3/N1 attenuation, more blinks), and within-person classifiers reach about 0.70–0.88 AUC on research EEG, dropping to about 0.57–0.70 across people. The direction of the alpha change is contested, so a model calibrated to each person is needed. Muse-specific mind-wandering detection evidence is limited to small mindfulness-feedback pilots.

### Cited Findings
- Braboszcz & Delorme (2011): during mind-wandering in breath-focus meditation, theta and delta increased and alpha and beta decreased relative to breath focus (canonical; DOI from prior knowledge, not re-fetched). — [NeuroImage 2011](https://doi.org/10.1016/j.neuroimage.2010.10.008)
- A bioRxiv experience-sampling study in novice meditators found decreased alpha during mind-wandering and mixed theta results. Other studies found alpha greater during mind-wandering, with unaware mind-wandering adding delta/theta increases. The direction of the alpha effect conflicts across studies. — [bioRxiv 2020.10.23.351759](https://www.biorxiv.org/content/10.1101/2020.10.23.351759.full.pdf); [Frontiers Hum Neurosci 2023](https://www.frontiersin.org/articles/10.3389/fnhum.2023.1182319/full)
- Dong, Mills, Knight & Kam (2021, PLoS ONE): n=13 modeled, 64-channel BioSemi, ERP-only features (N1, P3) in an auditory oddball. Within-participant SVM: AUC 0.715 (range 0.452–0.995), accuracy 0.643. Across-participant: AUC 0.613, accuracy 0.591. P3 was the best single feature but only slightly above chance; some individuals' models were below chance. — [PLoS ONE 2021](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0251490)
- Riemannian covariance features (delta–beta) during lectures: within-participant SVM AUC 0.876, falling to 0.703 when tested across lectures. — [Frontiers Hum Neurosci 2023](https://www.frontiersin.org/articles/10.3389/fnhum.2023.1182319/full)
- HMM-based detection during video learning: within-participant AUC 0.888 (abstract/snippet only). — [ResearchGate 2023](https://www.researchgate.net/publication/371229289_Mind_wandering_state_detection_during_video-based_learning_via_EEG)
- Force-control task: spectral plus synchronization features gave 75.53% within-participant and 71.57% cross-participant accuracy. — [Frontiers Neurosci 2025](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2025.1654827/full)
- EEG plus facial video (random forest): within-participant AUC 0.68, across-participant AUC 0.57. — [Behavior Research Methods 2025](https://link.springer.com/article/10.3758/s13428-025-02847-4)
- Task-general mind-wandering prediction across tasks with EEG (Jin, Borst & van Vugt 2019); exact accuracies not verified this session. — [ResearchGate: Predicting task-general mind-wandering with EEG](https://www.researchgate.net/publication/331625859_Predicting_task-general_mind-wandering_with_EEG)
- Benchmark: 14 mind-wandering datasets, 13 models, modalities EEG/eye/face/physiology. It notes prior results were inconsistent because models, preprocessing and metrics differed (abstract only; modality accuracies not retrieved). — [Bodonhelyi et al., arXiv 2604.09569](https://arxiv.org/pdf/2604.09569)
- Blink rate: Smilek, Carriere & Cheyne (2010). During reading, mind-wandering episodes had more blinks and fewer fixations; blink rate was higher in the 5 s before mind-wandering reports (t(11) = 4.25, p = .001, n=12). Causal direction unclear. — [Psychological Science 2010 (ResearchGate)](https://www.researchgate.net/publication/44679493_Out_of_Mind_Out_of_Sight_Eye_Blinking_as_Indicator_and_Embodiment_of_Mind_Wandering)
- A later review concludes blink rate and duration correlate positively with mind-wandering; a 2026 SART study found more blinks and slower RTs during mind-wandering in meditators and non-meditators. — [Consciousness & Cognition accepted manuscript](https://www.sciencedirect.com/science/article/am/pii/S1053810022000356); [Current Psychology 2026](https://link.springer.com/article/10.1007/s12144-026-09946-1)
- Eye-movement amplitude (delta band, 1–4 Hz, from EOG) was smaller during focused-attention meditation than during instructed mind-wandering. This is directly relevant because AF7/AF8 pick up EOG. — [PMC6345481](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6345481/)
- Muse studies: a pilot of Muse (AF7/AF8/TP9/TP10) mindfulness neurofeedback in children reported increased "calm/focused" states and redirection of attention when it wandered (exploratory, uncontrolled). It cites Hunkin et al. as finding less mind-wandering with Muse-assisted training (not checked). A Muse-based Juingong meditation study compared meditation with instructed mind-wandering using a theta/alpha index. — [PMC8774020](https://pmc.ncbi.nlm.nih.gov/articles/PMC8774020/); [PMC8835034](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8835034/)

### Inferences
- On Muse, blink rate and blink/eye-movement amplitude from AF7/AF8 are probably the most robust mind-wandering features. Blinks dominate those channels anyway, and the literature supports a within-person increase in blinks during mind-wandering. The artifact becomes a feature.
- Alpha at TP9/TP10 (temporo-parietal, nearer posterior alpha generators) is the best available spectral feature. Because the sign of the alpha effect varies by study and task (eyes-closed meditation vs reading), it must be learned per person from experience-sampling probes, not hard-coded.
- Realistic expectation: with per-user calibration from roughly 20–50 thought-probe labels, about 0.65–0.75 AUC on Muse. Cross-user models would be near 0.55–0.65. This estimate extrapolates from research-grade results downward, given Muse's lower signal quality.

### Gaps
- No peer-reviewed study was found reporting Muse-specific mind-wandering classification accuracy against thought probes.
- The Hunkin et al. Muse study was not verified.
- Per-modality accuracies from the 2026 benchmark (arXiv 2604.09569) were not retrieved.

---

## 5. Which states are realistically detectable per-person, which are only trait/group-level, which are not feasible; artifact confounds

### Takeaway
Per-person with calibration (moderate confidence): mind-wandering/attentional lapses (blinks + alpha + IMU stillness) and general physiological arousal/stress (HR up, RMSSD down vs personal baseline). Only group/trait-level: FAA for depression or approach motivation, resting-HRV differences in anxiety or rumination, resting fNIRS HbO and anxiety. Not feasible as continuous passive detection: rumination specifically (vs other negative or effortful states), spontaneous craving (ERP markers need cues), and FMθ (no midline electrode). Dry-electrode artifacts (EMG at TP9/TP10, EOG at AF7/AF8) are the dominant confound and overlap with the very bands the claims rest on.

### Cited Findings
- Muse signal quality: in a 2025 consumer vs research-grade comparison, Muse showed the poorest signal quality and very low alignment with the reference; attributed partly to flat silver-ink electrodes. — [PMC11679099](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11679099/)
- Muse signal quality is "disturbed by muscle tension," and consumer headsets "suffered greatly" from eye-blink artifacts. Dry electrodes are more susceptible to movement artifact, 50/60 Hz interference and sweat drift. Alpha features are relatively robust because alpha is prominent and separable from artifacts. — [Gel vs consumer dry electrodes (PMC10873917)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10873917/); [Ratti et al. 2017, Front Hum Neurosci](https://www.frontiersin.org/journals/human-neuroscience/articles/10.3389/fnhum.2017.00398/full); [Consumer-grade EEG quality review (NeuroIS)](https://www.researchgate.net/publication/346407183_Consumer-Grade_EEG_Instruments_Insights_on_the_Measurement_Quality_Based_on_a_Literature_Review_and_Implications_for_NeuroIS_Research)
- Muse can measure ERPs (N200, P300, reward positivity) when stimuli are presented by the app. — [Krigolson et al. 2017 (PMC5344886)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5344886/)
- Between-subject vmHRV differences in perseverative cognition are non-significant, but within-subject reactivity is reliable, which supports a design based on deviation from the person's own baseline. — [Int J Psychophysiol 2026 (abstract)](https://www.sciencedirect.com/science/article/abs/pii/S0167876026000516)
- FAA has a null meta-analytic association with depression. — [van der Vinne et al. 2017](https://www.semanticscholar.org/paper/Frontal-alpha-asymmetry-as-a-diagnostic-marker-in-A-Vinne-Vollebregt/22a0a94b8b91e42acfcf8ce3925d62164c1deb6d); [eLife 2021](https://elifesciences.org/articles/60595)

### Inferences (state-by-state feasibility matrix)
| Target state | Best Muse-feasible markers | Level | Feasibility with per-user calibration |
|---|---|---|---|
| Mind-wandering / distraction | Blink rate and EOG amplitude (AF7/AF8), alpha/theta at TP9/TP10, IMU stillness/fidget | State | Moderate (≈0.65–0.75 AUC plausible; extrapolated) |
| Acute stress / arousal | HR ↑, RMSSD/HF ↓ vs personal baseline (PPG); possibly beta/EMG ↑ (muscle tension); IMU fidget | State | Moderate for "arousal," low for "anxiety" specifically (arousal ≠ anxiety; exercise, excitement and caffeine confound) |
| Rumination / RNT | vmHRV ↓ during episodes; no reliable EEG signature | State (HRV) / trait (EEG) | Low; can flag "sustained low-HRV, low-movement" periods as a reflection prompt but cannot identify rumination |
| Craving (spontaneous) | None validated passively | — | Not feasible |
| Craving (cue-probe task) | P300/LPP to personal cues vs neutral, averaged over trials | Session-level | Feasible as an assessment exercise; reliability per person unknown |
| Depression / anxiety (trait) | FAA, resting HRV, resting HbO | Trait/group | Not appropriate for a non-medical tool; FAA is not replicated |

- Artifact confounds: TP9/TP10 sit over the temporalis muscle, so jaw clenching, chewing, talking and frowning produce broadband EMG that inflates beta/gamma (>15–20 Hz). These are the same bands often claimed for "stress" or "rumination." Muscle tension may correlate with stress, so a beta-based stress feature is partly an EMG feature. AF7/AF8 are near the eyes, so blinks and saccades dominate delta/theta (<8 Hz) there, making frontal theta claims unreliable without EOG regression. Pulse artifacts and forehead blood flow also affect the optical channels.
- The IMU should be used both as a feature (fidgeting/restlessness for anxiety; stillness during mind-wandering in seated tasks) and as an artifact gate (discard EEG/PPG/fNIRS windows with head motion).

### Gaps
- No quantitative study of jaw/temporalis EMG contamination specifically at Muse TP9/TP10 was found in this session.
- No validation of Muse S Athena optics (PPG HRV accuracy vs ECG; fNIRS vs research fNIRS) was found.

---

## 6. Multimodal fusion: does combining EEG + HRV + fNIRS + motion improve state detection?

### Takeaway
Reviews consistently report that fusion improves stress-detection accuracy over single modalities (e.g., HRV + EEG beating HRV alone), but most of the evidence comes from small lab samples with within-study validation. Generalization gaps are a recurring problem. No published study was found fusing Muse-style 4-channel EEG with forehead fNIRS, PPG and IMU for these states.

### Cited Findings
- Systematic review of multimodal wearable stress detection (2021–2025): HRV-based anxiety/stress detection showed "superior outcomes" when combined with EEG. Fusing EDA with HRV reduced single-sensor uncertainty, and one fusion study reached 96.25% accuracy. The review's framing emphasizes validation protocols and generalization gaps (abstract/snippet only). — [ResearchGate systematic review](https://www.researchgate.net/publication/400176932_Multimodal_Wearable-Based_Stress_Detection_Using_Machine_Learning_A_Systematic_Review_of_Validation_Protocols_and_Generalization_Gaps_2021_-_2025)
- Mental-stress review (MDPI Sensors 2026): HRV models need artifact handling and/or multimodal fusion for robustness. It lists an ECG+EEG ANN study reporting 95% accuracy with only 20 subjects. — [MDPI Sensors 2026](https://www.mdpi.com/1424-8220/26/5/1616)
- Multimodal wearable stress detection results (arXiv 2025) and newer attention-based fusion architectures (arXiv 2026) (abstract-level only). — [arXiv 2508.10468](https://arxiv.org/pdf/2508.10468); [arXiv 2611.01974](https://arxiv.org/pdf/2611.01974)
- Fusing heart rate, EDA, respiration and skin temperature detected stress better than any single signal (autism stress-monitoring review). — [MDPI Sensors 2024](https://www.mdpi.com/1424-8220/24/24/8137)
- WESAD benchmark (chest + wrist sensors, lab stress induction): the canonical multimodal stress dataset. It reported that multimodal combinations generally outperform single modalities, with binary stress vs non-stress accuracies in the ~90% range for chest signals (canonical; DOI from prior knowledge, not re-fetched; exact figures should be checked). — [Schmidt et al. 2018, ICMI](https://doi.org/10.1145/3242969.3242985)
- Mind-wandering: EEG plus facial video gave only 0.68 within-person and 0.57 cross-person AUC, so fusion did not produce strong performance there. — [Behavior Research Methods 2025](https://link.springer.com/article/10.3758/s13428-025-02847-4)

### Inferences
- For Muse S Athena, the expected gains from fusion come mostly from:
  1. PPG-HRV as the arousal backbone.
  2. IMU for artifact gating and fidget features.
  3. EEG blink/alpha features for attention.

  Forehead fNIRS likely overlaps heavily with PPG/systemic signals and should be treated as experimental until shown to add independent variance on the user's own data.
- Reported fusion accuracies (95–96%) come from lab stressors (Trier/arithmetic tasks) with strong arousal contrasts. Real-world self-reported anxiety, rumination or craving produce far subtler and confounded signals, so field accuracy will be substantially lower.

### Gaps
- No fusion study was found combining 4-channel dry EEG with fNIRS, PPG and IMU on one headband (Muse S Athena-like) for anxiety, rumination, craving or mind-wandering.
- No ablation evidence was found quantifying fNIRS's incremental value over PPG on forehead-only systems.
- No prospective, real-world (ecological momentary assessment) validation of any consumer-headband state detector for these four states was found.
