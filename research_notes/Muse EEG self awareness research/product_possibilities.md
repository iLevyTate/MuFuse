# Product Possibilities: A Brain-Connected AI Companion (Muse S Athena + phone + glasses/ring + local journaling LLM)

Scope note: research done 2026-11-25 with a hard cap of about 15 tool calls, so coverage is broad, not deep. Items marked **[prior knowledge, not re-verified this session]** come from the researcher's background knowledge, with a stable DOI or URL given where possible. The report writer should treat them as lower confidence than items retrieved this session. Feature ideas appear under each question's Inferences, tagged **[Grounded]** (direct precedent or evidence), **[Extrapolated]** (precedent exists but has not been tested in this setting) or **[Speculative]**.

## 1. Comparable products and research prototypes (as of 2026): claims, validation, failures

### Takeaway
Consumer neurotech has split three ways. (a) Focus and meditation EEG wearables (Muse, Neurable/MW75, Emotiv MN8, Neurosity Crown) sell "wellness" metrics with thin independent validation. (b) Closed-loop sleep headbands (Elemind, Somnee) have small company-run trials showing faster sleep onset. (c) Research-grade fNIRS/EEG systems (Kernel Flow, MIT AttentivU) have stronger methods but small samples. The most relevant precedent for this project is Neurosity's September 2025 MCP server, which gives Claude live Crown brain data. That shows the "LLM plus EEG context" pattern now ships, but it is cloud-based, not local.

### Cited Findings
**Muse S Athena (the target hardware)**
- Launched March 2025 at $474.99 US / $574.99 CA. It is the 4th-generation InteraXon device and adds fNIRS to EEG. — [Gadgets & Wearables review](https://gadgetsandwearables.com/2025/04/14/muse-s-athena-review/); [Engadget](https://www.engadget.com/wearables/muses-new-wearable-eeg-knows-how-hard-youre-thinking-120041154.html)
- Hardware: four EEG sensors along the brow line and five optical sensors on the forehead for fNIRS. Same soft headband form factor as Muse S, so it can be worn during sleep. — [IEEE Spectrum](https://spectrum.ieee.org/muse-headband)
- Muse pairs the EEG and fNIRS data with an AI "Foundational Brain Model" said to be trained on more than 80,000 sessions. It added an "owl flight" game driven by mental effort, and keeps sleep tracking and recovery scoring. Some features need a subscription (G&W scored it 8.5/10). — [Gadgets & Wearables](https://gadgetsandwearables.com/2025/04/14/muse-s-athena-review/)
- IEEE Spectrum's sources credit its portability, affordability and ease of use, but say sensor limitations "could preclude its use for some research questions." Spectrum also disputes the "world's first consumer EEG+fNIRS" marketing claim. — [IEEE Spectrum](https://spectrum.ieee.org/muse-headband)
- Earlier Muse validation: Krigolson et al. (2017) showed the Muse can measure N200/P300 ERP components and reward positivity, which supports its use for some ERP research despite only four dry channels. — [Krigolson et al., Front. Neurosci. 2017](https://doi.org/10.3389/fnins.2017.00109) **[prior knowledge, not re-verified this session]**

**Neurable / Master & Dynamic MW75 Neuro**
- Launched late 2024 at $699, $100 more than the standard MW75. EEG sensors sit in the earcup cushions (described as 12 channels). Main pitch: focus tracking and prompts to take breaks before burnout. — [Engadget](https://www.engadget.com/audio/headphones/neurables-brainwave-tracking-master--dynamic-headphones-tell-you-when-to-take-a-break-120004736.html); [SlashGear review](https://www.slashgear.com/1677762/master-and-dynamic-mw75-neuro-review-headphones-eeg-audio-price-details)
- Reviews were mixed. BGR called it a cool concept but "too expensive and not that useful in this first version." Tom's Guide said it was "torn." SlashGear disliked needing two apps. — [BGR](https://bgr.com/reviews/master-dynamic-mw75-neuro-headphones-that-read-your-mind/); [Tom's Guide](https://tomsguide.com/audio/headphones/i-just-tested-these-headphones-that-can-read-your-brain-signals-and-im-torn)

**Neurosity Crown, SDK and LLM integration (closest precedent to this project)**
- Neurosity launched a free remote MCP server (mcp.neurosity.co) on 15 Sept 2025. Users add it as a custom connector in Claude, and because it is built on the Neurosity SDK it exposes everything the Crown records. — [Neurosity blog](https://neurosity.co/blog/introducing-the-neurosity-mcp)
- A community, MIT-licensed "bci-mcp" Python server streams EEG band powers and focus/calm ratios to Claude or any MCP client and claims to work with many devices. — [Hackaday.io](https://hackaday.io/project/206866-bci-mcp-live-eeg-brain-state-for-claude-over-mcp)
- A Fireship video from November 2025 showed Claude Code using Crown data as context. Coverage raised privacy concerns about sending brain data to a cloud AI. Source is a secondhand summary. — [Recapio summary](https://recapio.com/digest/this-neural-interface-writes-code-from-my-brain-waves-by-fireship)
- Most Crown comparison material online is Neurosity's own marketing ("guides"), so it is not independent. — e.g. [Neurosity guide: Crown vs Muse S](https://neurosity.co/guides/neurosity-crown-vs-muse-s)

**Emotiv MN8**
- 2-channel EEG earbuds with up to 6 hours of battery. Emotiv's disclaimer says its products are "not designed or intended to be used for diagnosis or treatment of disease." — [Emotiv MN8 product page](https://www.emotiv.com/products/mn8)

**Mendi (fNIRS neurofeedback)**
- Prefrontal-only fNIRS neurofeedback headband. The company says its signal has been validated against research-grade fNIRS in peer-reviewed studies; I did not check the underlying studies. — [Mendi science page](https://mendi.io/pages/science)
- Informal researcher opinion on the Connectionists mailing list (2024) called it "a toy." This is anecdotal, not a formal evaluation. — [Connectionists mailing list](https://mailman.srv.cs.cmu.edu/pipermail/connectionists/2024-September/042004.html)

**Elemind and Somnee (closed-loop sleep headbands)**
- Elemind ($349 plus app subscription) uses EEG-driven closed-loop acoustic stimulation. A company-reported trial says 76% of participants fell asleep faster, by 48% on average. An MIT-linked small study found 30 minutes of stimulation cut sleep onset by 10–15 minutes. The pilot authors call it feasibility, not proven efficacy. — [Sleep Review](https://sleepreviewmag.com/sleep-treatments/therapy-devices/neurostimulators/neurostimulation-headband-cuts-time-fall-asleep-half/); [MIT News](https://news.mit.edu/index%2Ephp/2024/startup-elemind-helps-people-fall-asleep-0925); [IEEE Spectrum](https://spectrum.ieee.org/elemind-neuromodulation); [GearJunkie review](https://gearjunkie.com/technology/elemind-sleep-headband-review)
- Somnee delivers personalized electrical stimulation in the theta and alpha bands, tuned to the user's peak frequency. Analysts note its trial compared against open-loop, non-personalized stimulation rather than sham, which is weaker evidence. Price is reported as both $429 and $299 (conflicting sources). — [Efferent analysis](https://efferent.substack.com/p/company-spotlight-elemind); [Tom's Guide](https://tomsguide.com/wellness/mattresses/this-brainwave-reading-headband-promises-sleep-on-demand-futuristic-dream-or-a-sci-fi-nightmare)

**Apple AirPods EEG**
- Apple filed a patent application (2023) for in-ear electrodes measuring EEG, EMG and EOG. It overprovisions electrodes and lets a model pick the best-signal subset per user. Sources disagree on whether and when it was granted. It is not a product. — [9to5Mac](https://9to5mac.com/2025/11/28/airpods-brain-signal-study-patent/); [PhoneArena](https://www.phonearena.com/news/Future-AirPods-may-read-brain-waves-and-other-biosignals-using-in-ear-electrodes_id149348)
- A November 2025 Apple research paper on self-supervised ear-EEG learning is unrelated to the patent and does not mention AirPods. — [9to5Mac](https://9to5mac.com/2025/11/28/airpods-brain-signal-study-patent/)

**MIT Media Lab: AttentivU and Dormio**
- AttentivU (Kosmyna & Maes): a headband version tested on 48 adults found that EEG biofeedback redirected attention and improved comprehension scores. The glasses version was tested on only 6 adults. — [MIT Media Lab publication](https://www.media.mit.edu/publications/attentivu-evaluating-the-feasibility-of-biofeedback-glasses-to-monitor-and-improve-attention-1/)
- AttentivU glasses carry EEG around the ear and EOG on the nose bridge (eye movement, blink rate). A later EEG+EOG+fNIRS glasses prototype reached 79% accuracy on cognitive load in a 14-person mental-arithmetic study, against 62% for EEG alone and 63% for fNIRS alone. That multimodal gain is directly relevant to the Athena's EEG+fNIRS combination. — [MIT Media Lab EEG/EOG/fNIRS glasses](https://www.media.mit.edu/projects/attentivu-eeg-eog-fnirs-glasses/overview/); [BSN'19 paper](https://www.media.mit.edu/publications/ttentivu-a-wearable-pair-of-eeg-and-eog-glasses-for-real-time-physiological-processing/)
- A related project, the AU monocle (adaptive AR glasses), responded only when attention was classified as "internal" (14 users). — [MIT Media Lab](https://www.media.mit.edu/projects/au-monocle/overview/)
- Dormio: tracks sleep onset and plays audio cues during hypnagogia (targeted dream incubation), and captures dream reports by voice without fully waking the user. Pilot n=6 (alt.CHI 2018). The 50-person follow-up, published in *Consciousness and Cognition* in 2020, reported incubated dream content and creativity benefits. Replications have run at Duke, Harvard, Boston College, Rochester and Chicago. — [MIT News](https://news.mit.edu/2020/targeted-dream-incubation-dormio-mit-media-lab-0721); [MIT Media Lab project](https://www.media.mit.edu/projects/sleep-creativity/overview/)

**Kernel Flow and Neurode**
- Kernel Flow validation work cited online used only two participants (secondary report). — [Physics World](https://physicsworld.com/a/could-optical-brain-imaging-helmets-be-the-future-of-wearable-technology/)
- Search returned a NeurIPS 2026 listing for a "600-channel wearable multimodal fNIRS-EEG headband with real-time attention decoding" that classifies attention as inward or outward. The search tool's summary attributed it to "Neurode," but this conflicts with my prior knowledge that Neurode is an Australian tDCS headband for ADHD and depression. The attribution is unverified. — [NeurIPS 2026 listing](https://neurips.cc/virtual/2026/174110)

### Inferences
- The project fits in an open gap. Neurosity proved demand for "brain data as LLM context" but runs it through a cloud MCP into general chat. Nobody I found combines (a) local LLM, (b) a longitudinal journal, (c) EEG+fNIRS, and (d) life context.
- The Athena's EEG+fNIRS combination resembles AttentivU's multimodal result (79% multimodal vs about 62–63% single modality for cognitive load). That supports fusing modalities rather than trusting any single "focus" number. **[Extrapolated]**: different hardware and task.
- The MW75 reviews suggest that a brain-sensing feature alone does not justify the purchase. Value has to come from what the data connects to, which favours the context-fusion and journaling angle.
- Feature idea **[Grounded: Dormio]**: "Hypnagogia capture" mode. The Athena is soft enough to sleep in. At EEG and IMU-detected sleep onset, bone-conduction glasses or the phone play a cue, and the user murmurs a report that the local LLM transcribes into the journal. Precedent: Dormio, which used a hand-worn glove sensor rather than EEG. Replicating the cue timing with Muse EEG would itself be an experiment.
- Feature idea **[Grounded: AttentivU, MW75]**: gentle haptic or bone-conduction nudges when attention drifts during a declared focus block. Precedent: AttentivU's n=48 comprehension result. **[Extrapolated]**: frontal-only Muse signals.

### Gaps
- Did not verify Frenz Brainband (Earable) status or validation; no results returned.
- Did not verify Kernel's 2024–2026 corporate status (layoffs or pivots).
- Did not confirm the Neurode identity conflict, or whether Neurable or Muse have discontinued product lines since 2025.
- No list of discontinued consumer neurotech in 2025–2026 was found. From prior knowledge (not verified this session), devices such as Melomind, Dreem (pivoted to clinical) and Kokoon have exited or pivoted; this needs checking.
- Muse's built-in blink and jaw-clench detection (historically exposed via the Muse SDK and Mind Monitor) was not re-verified for Athena's current SDK.

## 2. Context fusion: linking brain and body states to calendar, location, social, music, apps, sleep, caffeine, exercise, weather

### Takeaway
Personal informatics research says the hard part is not sensing but the "integration" and "reflection" stages. Data from many sources must be joined and correlations shown carefully, because correlations alone do not show causation. Systems that showed many correlations across streams (Mobile Health Mashups, Visual Cuts) found users valued them but needed help interpreting them. The safest design treats any correlation as a hypothesis to test (see Q3), not as an insight.

### Cited Findings
- Li, Dey & Forlizzi's stage-based model (CHI 2010) describes five stages: preparation, collection, integration, reflection, action. It identifies barriers that cascade between stages; integration across data sources is a major one. — [Li et al. 2010, DOI](https://doi.org/10.1145/1753326.1753409) **[prior knowledge, not re-verified this session]**
- Epstein et al.'s "lived informatics" model (UbiComp 2015) adds deciding to track, selecting tools, and lapsing or resuming. Real tracking is messy and episodic, so systems must tolerate gaps and abandonment. — [Epstein et al. 2015, DOI](https://doi.org/10.1145/2750858.2804250) **[prior knowledge, not re-verified this session]**
- Choe et al. (CHI 2014) studied Quantified Self practitioners. They describe Mobile Health Mashups, which displayed statistically significant correlations across exercise, weight, food, sleep and mood streams. — [Choe et al. 2014 PDF](https://pubweb.eng.utah.edu/~cs5540/au16/readings/PersonalInformatics-Choe2014.pdf)
- Epstein's dissertation work on "Visual Cuts" surfaced correlations in personal tracking data and treated finding correlations as part of the reflection work. — [UW dissertation](https://digital.lib.washington.edu/researchworks/bitstreams/c791fe4c-ebc3-4708-b5c6-ae111d5a0dde/download)
- Daskalova et al. (UbiComp 2017) say outright that self-tracking can surface correlations, but establishing causation needs self-experimentation. — [Daskalova et al. UbiComp'17](https://jeffhuang.com/papers/SelfExperiments_UbiComp17.pdf)
- The StudentLife study (Wang et al., UbiComp 2014) passively sensed sleep, conversation, activity and location from smartphones and correlated them with depression, stress and GPA. It is a precedent for phone-context plus wellbeing fusion. — [Wang et al. 2014, DOI](https://doi.org/10.1145/2632048.2632054) **[prior knowledge, not re-verified this session]**
- Google's Personal Health Insights Agent (PHIA) uses code generation, web search and iterative reasoning to answer open questions over wearable data. It was evaluated on more than 4,000 questions and published in *Nature Communications* (Jan 2026). It is evidence that an LLM should compute statistics with code rather than "eyeball" data. — [PHIA, PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12855967); [arXiv 2406.06464](https://arxiv.org/abs/2406.06464v3)
- Google's Personal Health Agent framework splits the job into data-science, domain-expert and health-coach sub-agents. — [Google Research blog](https://research.google/blog/the-anatomy-of-a-personal-health-agent/); [arXiv 2508.20148](https://arxiv.org/pdf/2508.20148v2)

### Inferences
- Architecture implication **[Grounded: PHIA]**: the local LLM should never compute correlations "in its head." It should call deterministic analysis tools (Python or SQL over the timeline) and narrate the outputs with their uncertainty. PHIA's code-generation design supports this.
- Guarding against spurious patterns (design rules drawn from the above, **[Extrapolated]**):
  1. Pre-register a small set of hypotheses the user cares about, rather than mining every pair of streams.
  2. If the system does mine, apply false-discovery-rate correction and show how many comparisons were tried.
  3. Require a minimum number of exposure days in each condition.
  4. Show raw within-person time series alongside any summary.
  5. Label every surfaced pattern as "hypothesis, not finding" and offer a one-tap path to turn it into an N-of-1 experiment (Q3).
- Feature idea **[Extrapolated: StudentLife, Mashups]**: a "context-tagged brain timeline." Each Muse session or passive wear window is automatically tagged with calendar event type (meeting or solo), location class, music playing, foreground app category, last caffeine log, steps, sleep from the previous night, and weather. The journal then asks: "Your relaxation markers were lower in the last three 1:1 meetings with X than in other meetings. Want to note anything about those?"
- Feature idea **[Speculative]**: "Urge forensics." When the phone detects a compulsive app open (fast unlock, then social app), the system timestamps the last two minutes of EEG, fNIRS and HRV for later reflection: what was the body doing right before the urge? There is no direct validated precedent for EEG markers of phone urges on frontal-only Muse; this is purely exploratory.
- Feature idea **[Extrapolated]**: an "attention budget" view, accumulating time-in-focus estimates against calendar load to show which days overspend. MW75/Neurable's break-prompt framing is the product precedent, but validity on Muse is untested.
- Lived-informatics implication: expect lapses. The companion should welcome the user back after a gap without guilt, and analyses must handle missing data.

### Gaps
- Found no peer-reviewed study that combined consumer EEG with calendar, app usage and music context in the wild. This looks like genuine white space, but also means no evidence that the correlations hold up.
- Did not find a paper that specifically measures spurious-correlation or false-discovery harms in personal informatics tools; the multiple-comparisons guidance above is my inference.
- Did not retrieve research on weather or caffeine effects on consumer EEG metrics.

## 3. N-of-1 / single-case experimental designs and personal science

### Takeaway
There is mature methodology (the CENT reporting guideline) and working open-source tooling (StudyU for researcher-designed trials, StudyMe for self-designed ones) for N-of-1 trials. UbiComp work shows novices can run valid self-experiments with structured guidance. A user-facing "experiment builder" is therefore well grounded. The Muse-specific outcome measures (for example a "rumination marker") are the weak link and must be framed as exploratory.

### Cited Findings
- StudyU (Hasso Plattner Institute; JMIR 2022) is an open-source platform. A web "Designer" lets people specify, publish and run digital N-of-1 trials, and a smartphone or web participant app runs without an account. The authors note that running a digital N-of-1 trial previously meant building a new app. — [StudyU, JMIR 2022 (PMC)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9297132/); [StudyU v2 GitHub](https://github.com/HIAlab/studyu-v2)
- The same group's StudyMe app guides individuals to create and run their own fully customized N-of-1 trials. — [arXiv 2108.00320](https://arxiv.org/pdf/2108.00320.pdf)
- A registered Weill Cornell pilot (NCT07252310, updated Feb 2026) tests StudyU's acceptability and feasibility for N-of-1 trials in heart-failure patients, a sign of continued clinical uptake. — [ClinicalTrials.gov NCT07252310](https://clinicaltrials.gov/study/NCT07252310)
- "Digital N-of-1 Trials and their Application in Experimental Physiology" (2024) reviews using wearable physiological outcomes in N-of-1 designs. — [arXiv 2412.15076](https://arxiv.org/pdf/2412.15076)
- Daskalova et al. (UbiComp 2017) analyzed two cohorts of novice self-experimenters. The core challenge was designing scientifically valid self-experiments that reach conclusive results, which motivates guided designs (randomization, washout, adequate duration). — [Daskalova et al. UbiComp'17](https://nediyana.github.io/pdfs/SelfExperimentsPaper.pdf)
- The CENT 2015 statement (BMJ) is the CONSORT extension for reporting N-of-1 trials, covering randomized or balanced period order, washout, blinding where possible, and per-period outcome reporting. — [Vohra et al. BMJ 2015, DOI](https://doi.org/10.1136/bmj.h1738) **[prior knowledge, not re-verified this session]**
- Open Humans is a nonprofit platform for participant-centred research and personal data exploration (Greshake Tzovaras et al., GigaScience 2019). It is a possible precedent for opt-in, user-controlled data sharing. — [DOI](https://doi.org/10.1093/gigascience/giz076) **[prior knowledge, not re-verified this session]**

### Inferences
- Feature idea **[Grounded: StudyMe/StudyU, CENT]**: a "Be your own scientist" experiment wizard driven by the LLM. Example: "Does a morning walk change my afternoon focus or calm scores?"
  - The LLM helps phrase a single testable question, picks an outcome (for example the Muse calm % in a fixed 5-minute 2 pm check-in, plus a 1-item self-rating) and proposes an ABAB or randomized-day schedule with enough days per arm.
  - The phone randomizes each morning and the ring logs compliance with one tap.
  - The tool layer, not the LLM, computes effect size with a confidence or credible interval.
  - The journal gets a plain-language result that states "inconclusive" when it is.
- Standardized measurement windows **[Extrapolated: ERP validation and lab protocols]**: EEG band power is highly state- and artifact-dependent. Experiments should use a fixed, short, eyes-closed or task-based "probe" session at the same time of day, not passive all-day wear. This turns noisy EEG into a more repeatable within-person outcome.
- Dual outcomes: always pair a neural or physiological outcome with a self-report outcome. If they disagree, that is useful data, and it keeps the user from deferring to the device over their own experience.
- Feature idea **[Speculative]**: "Experiment library" sharing. Users could export de-identified protocols (not raw neural data) Open Humans-style, so others can replicate a self-experiment. That would create something like a community replication culture.

### Gaps
- No source found on minimum detectable effect or test-retest reliability of Muse band-power metrics day to day, which is needed to size N-of-1 trials honestly.
- Did not check whether StudyU or StudyMe can ingest wearable or EEG streams, or only questionnaires.
- No validated "rumination marker" from frontal 4-channel EEG was found. The user's example outcome should be operationalized as self-report plus exploratory EEG and fNIRS.

## 4. LLM-based journaling, reflective companions, memory, and keeping interpretations humble

### Takeaway
Peer-reviewed deployments (MindfulDiary, CHI 2024) show LLM-guided conversational journaling sustains journaling and gives clinicians richer context. They also flag safety and controllability concerns, addressed through a state-based (scripted-stage) conversation design. For long-term memory, the generative-agents "memory stream" pattern (timestamped observations, importance scores, retrieval, periodic reflection) suits a personal timeline. Agent work on wearable data shows the LLM should delegate numbers to code.

### Cited Findings
- MindfulDiary (Kim et al., CHI 2024) is an LLM journaling app with a state-based conversation flow that follows expert guidelines while allowing free conversation, plus a clinician dashboard. In a 4-week field study, 28 patients with major depressive disorder and 5 psychiatrists took part. Patients enriched their daily records consistently, and clinicians reported better empathy from understanding patients' daily context. — [arXiv 2310.05231](https://arxiv.org/abs/2310.05231v2)
- A CHI 2024 HEAL workshop paper reflecting on the MindfulDiary deployment discusses LLM safety and controllability concerns in clinical settings. — [HEAL workshop paper](https://heal-workshop.github.io/papers/25_evaluating_and_auditing_llm_dr.pdf)
- Generative Agents (Park et al., 2023) introduced a memory stream with retrieval scored by recency, importance and relevance, plus periodic "reflection" that writes higher-level summaries back into memory. It is the standard template for long-term companion memory. — [arXiv 2304.03442](https://arxiv.org/abs/2304.03442) **[prior knowledge, not re-verified this session]**
- Kocielnik et al.'s "Reflection Companion" (IMWUT 2018) was a mobile conversational system that prompted reflection on activity-tracker data with mini-dialogues. Users reported increased awareness and reflection. It is a direct precedent for "chatbot asks about your sensor data." — [DOI 10.1145/3214273](https://doi.org/10.1145/3214273) **[prior knowledge, not re-verified this session]**
- PHIA (Nature Communications 2026) shows that agents grounding answers in generated code over the user's wearable data, rather than free-text reasoning, are the current state of the art for numeric personal health questions. — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12855967)

### Inferences
- Memory architecture **[Grounded: Generative Agents, PHIA]**: two stores.
  1. A structured time-series and event store (EEG/fNIRS summaries, context tags, experiment logs) queried by tools.
  2. A text memory stream (journal entries, LLM reflections) with embedding retrieval.
  Weekly "reflection" passes write summaries, each citing the source entries and data windows it used.
- Humility mechanisms **[Extrapolated: MindfulDiary's state-based control and the neuro-hype literature in Q6]**:
  - The LLM may only describe a brain metric in observational language ("your alpha-band relative power was higher") plus the vendor's label, never as a mind-reading claim ("you were anxious").
  - Every interpretive statement is phrased as a question back to the user ("Did that meeting feel draining?").
  - The user's self-report always outranks the sensor.
  - Each insight shows its provenance (data window, number of sessions, signal-quality flags).
  - A "signal quality gate" blocks interpretation of artifact-heavy segments.
- Feature idea **[Grounded: Reflection Companion, MindfulDiary]**: evening "bookend" journaling. The LLM opens with 2–3 data-anchored prompts ("Your longest calm stretch today was during the 3 pm walk; anything notable?"), then follows the user's lead.
- Feature idea **[Extrapolated]**: "Time-travel retrieval." The user asks "When did I last feel like this?" The system retrieves past journal entries with similar text embedding and similar physiological signature, and presents both, explicitly marking the physiological similarity as weak evidence.
- Feature idea **[Speculative]**: "Letters from past self." The LLM surfaces a year-ago journal entry along with the physiological context of that day as a reflective prompt. No direct study found.
- Local LLM is a privacy differentiator against the Neurosity cloud MCP (Q1) and aligns with neural-data laws (Q6).

### Gaps
- Did not retrieve 2025–2026 CHI/CSCW papers on long-term (more than 3 months) LLM journaling deployments, or on harms such as over-reliance or sycophancy in reflective chatbots.
- No study found on how users interpret LLM narration of their EEG data specifically (whether trust is calibrated).

## 5. Novel interaction ideas with evidence: blink/jaw input, hypnagogia, meditation depth, flow, attention budget, sonification, shared sessions

### Takeaway
The best-evidenced novel interactions are (1) sleep-onset audio cueing and dream capture (Dormio, replicated across universities), (2) closed-loop audio during sleep onset (Elemind), (3) attention biofeedback via unobtrusive cues (AttentivU), and (4) EEG/EOG artifacts (blinks, jaw clench) as deliberate input, a long-standing BCI practice. "Flow detection" and "meditation depth" are the least validated on 4-channel consumer EEG and should be treated as exploratory.

### Cited Findings
- Dormio: sleep-onset detection triggers audio cues, and dream reports are captured by voice without full waking. This enables repeated incubation rounds and supports creativity augmentation (pilot n=6; follow-up n=50; replications at five universities). — [MIT News](https://news.mit.edu/2020/targeted-dream-incubation-dormio-mit-media-lab-0721); [MIT BCS News](https://bcs.mit.edu/news/new-way-control-experimentation-dreams)
- Elemind closed-loop acoustic stimulation timed to EEG shortened sleep onset in small studies (company and MIT-linked). This shows phase- or state-aware audio from a headband is feasible. — [MIT News](https://news.mit.edu/index%2Ephp/2024/startup-elemind-helps-people-fall-asleep-0925); [IEEE Spectrum](https://spectrum.ieee.org/elemind-neuromodulation)
- AttentivU EOG on the nose bridge tracks eye movement and blink rate, and its feedback redirected attention (n=48 headband). — [MIT Media Lab](https://www.media.mit.edu/publications/attentivu-evaluating-the-feasibility-of-biofeedback-glasses-to-monitor-and-improve-attention-1/); [MIT Spectrum](https://betterworld.mit.edu/spectrum/issues/spring-2022/mit-integrated-learning-initiative-project-focuses-on-focus)
- The AU monocle adapted AR content according to whether attention was classified as internal or external (14 users). It is a precedent for "don't interrupt when the user is inward-focused." — [MIT Media Lab](https://www.media.mit.edu/projects/au-monocle/overview/)
- Muse's owl-flight "mental effort" game (Athena) is a vendor precedent for real-time EEG+fNIRS-driven interaction. — [Gadgets & Wearables](https://gadgetsandwearables.com/2025/04/14/muse-s-athena-review/)
- Neurosity's MCP lets an LLM query live brain-state metrics, a precedent for "LLM checks your focus before deciding to interrupt you." — [Neurosity blog](https://neurosity.co/blog/introducing-the-neurosity-mcp)

### Inferences
Feature catalogue (each tagged):
1. **Hands-free micro-input [Grounded]**: a deliberate double jaw clench or triple blink on Muse's TP9/TP10 and AF7/AF8 means "bookmark this moment." It drops a context-rich marker into the journal ("tag: this conversation mattered"). It is robust because it uses large EMG/EOG artifacts rather than subtle brain signals. The BLE ring/clicker is the reliable fallback, and the two could cross-confirm. Precedent: AttentivU EOG, the general BCI artifact-as-input practice, and Muse's historical blink/jaw detection (not re-verified).
2. **Hypnagogia journal [Grounded: Dormio]**: see Q1. Add a nap-time "idea incubation" mode. The user sets a problem, bone-conduction audio repeats it at sleep onset, and voice reports go to the journal. The LLM can then cluster incubated ideas over weeks.
3. **Interruptibility guard [Extrapolated: AU monocle, Neurosity MCP]**: the phone holds non-urgent notifications while EEG, fNIRS and IMU suggest sustained focus during a calendar-declared work block, then releases them at the next natural break. The feedback rule is "defer, don't block," keeping the user in control.
4. **Calm sonification [Grounded: Muse app's real-time audio feedback during meditation is a long-standing product feature, prior knowledge]**: extended to ambient bone-conduction sonification during walks or work, mapping slow trends (not noisy instant values) to subtle soundscape changes. **[Extrapolated]** outside meditation.
5. **Meditation depth and progress tracking [Extrapolated]**: report per-session trends with confidence bands, framed as "consistency of the signal you trained on," not "depth of meditation." Validity of a depth construct on frontal 4-channel EEG is not established in sources found.
6. **Flow-state detection [Speculative]**: frontal EEG plus fNIRS plus behavior (app focus duration, typing cadence) could produce a "possible flow" flag that the user confirms or rejects in the evening, building a personally labelled dataset over time. No validated consumer flow detector was found.
7. **Shared or social sessions [Speculative]**: two Muse users meditating "together" remotely see a co-presence visualization of each person's calm trend (not raw data). Precedent only in art and research installations (not retrieved); privacy consent per session is essential.
8. **Cognitive-load-aware LLM [Extrapolated: AttentivU multimodal 79% result]**: the companion shortens or simplifies its spoken replies through bone-conduction glasses when fNIRS and EEG suggest high load. Users can turn this off.

### Gaps
- Did not retrieve peer-reviewed accuracy figures for blink or jaw-clench detection on the Muse specifically.
- Did not find research on EEG flow detection, meditation-depth validation, or brain-state sonification with consumer headbands (search budget exhausted).
- No evidence retrieved on shared or "hyperscanning" consumer experiences.

## 6. Risks of over-interpretation, neuro-hype, regulation and neurorights

### Takeaway
Most consumer neurotech claims are "wellness and enhancement" framed and lack controlled evidence. Neurofeedback benefits largely fail to beat placebo in double-blind, sham-controlled studies. Regulators (FTC) have been slow. Meanwhile US states (Colorado 2024, California 2024, Montana 2025, Connecticut effective July 2026) now classify neural data as sensitive, requiring express consent and deletion rights. A local-first, consent-explicit, humble-claims design is both the ethical and the strategic choice.

### Cited Findings
- Illes and colleagues (*Neuron*, 2019) found most direct-to-consumer brain-device claims were wellness or enhancement ("ease stress," "improve concentration"). Nine devices made health claims, and some firms appeared to frame claims as wellness to avoid regulatory scrutiny. — [The Scientist](https://www.the-scientist.com/do-devices-that-monitor-or-zap-the-brain-live-up-to-their-claims---66021); [Yahoo/STAT coverage](https://news.yahoo.com/cavalier-approach-experts-urge-companies-083504987.html)
- Wexler & Thibault argued that consumer EEG firms lean on neurofeedback literature in which nearly all adequately controlled studies point to "little more than an interesting placebo effect." Thibault's review reportedly found only 11 double-blind, sham-controlled studies among more than 3,000 publications (secondary figure, not verified against the original). — [The Scientist](https://www.the-scientist.com/do-devices-that-monitor-or-zap-the-brain-live-up-to-their-claims---66021)
- Critics question both the accuracy of consumer readings and the scientific basis for drawing conclusions from them. "Regulation and validation completely lags behind the industry" (ethicist quoted by Axios). — [Axios](https://www.axios.com/2019/06/20/flimsy-promises-brain-wearables); [Harvard Health](https://www.health.harvard.edu/blog/brain-based-devices-how-well-do-they-work-2019080117426)
- A more favourable counterpoint: a systematic review of 57 studies (more than 1,000 participants) reportedly found moderate-to-good sensitivity for EEG detection of mental fatigue. This is a secondary summary and the original was not verified. — [Techwalla summary](https://www.techwalla.com/13779420/brain-fitness-tracker-claims-vs-evidence-what-buyers-should-know)
- Wellness framing dominates: more than one-third of consumer neurotech companies (more than half in the US) target wellness applications. — [CFG "Promise and Peril"](https://cfg.eu/promise-and-peril/)
- FTC precedent: Lumos Labs (Lumosity) paid $2M in 2016 to settle FTC deceptive-advertising charges over unsupported brain-training claims. It is the template for how the FTC treats cognitive-benefit claims. — [FTC press release](https://www.ftc.gov/news-events/news/press-releases/2016/01/lumosity-pay-2-million-settle-ftc-deceptive-advertising-charges-its-brain-training-program) **[prior knowledge, not re-verified this session]**
- US state neural-data laws:
  - Colorado's HB24-1058 (signed 17 April 2024) adds biological and neural data to "sensitive data" under the Colorado Privacy Act.
  - California's SB 1223 adds neural data to CCPA sensitive personal information.
  - Montana's SB 163 (signed 1 May 2025, effective 1 Oct 2025) amends its Genetic Information Privacy Act.
  - Connecticut's amendment takes effect 1 July 2026.
  - Colorado and Montana require express consent to collect and separate consent or opt-out for third-party transfer, and all three states (CO, CA, MT) grant deletion rights.
  - The laws explicitly cover consumer headphones and earbuds that send brain data to apps.
  — [KFF Health News](https://kffhealthnews.org/news/article/colorado-california-montana-states-neural-data-privacy-laws-neurorights/); [Cooley neurotech legislation update](https://www.cooley.com/-/media/cooley/pdf/neurotech-laws-and-legislation-update-pdf.pdf)
- Several US Senate Democrats asked the FTC to investigate neural-data practices, and the AMA called for greater regulation. More states (e.g. Vermont H.814, testimony April 2026) were considering bills in 2026. — [KFF Health News](https://kffhealthnews.org/news/article/colorado-california-montana-states-neural-data-privacy-laws-neurorights/); [Vermont legislature testimony](https://legislature.vermont.gov/Documents/2026/Workgroups/Senate%20Health%20and%20Welfare/Bills/H.814/Witness%20Testimony/H.814~Ashley%20Collins~US%20State%20Legislation%20to%20Protect%20Neural%20Data~4-9-2026.pdf)
- Kosmyna (AttentivU lead) gave testimony to the German Ethics Council (Ethikrat) hearing on 18 Sept 2025, a sign that neurotech ethics is now on national agendas. — [Ethikrat PDF](https://www.ethikrat.org/fileadmin/PDF-Dateien/Veranstaltungen/anhoerung-2025-09-18-kosmyna.pdf)
- Privacy concern specifically about streaming Crown brain data into a cloud AI tool was raised in coverage of the Neurosity/Claude demo. — [Recapio summary](https://recapio.com/digest/this-neural-interface-writes-code-from-my-brain-waves-by-fireship)

### Inferences
- Design principles **[Grounded in above]**:
  1. Local-first processing and storage of raw neural data. Only derived, user-approved summaries go to any cloud.
  2. Explicit, granular consent screens modelled on the Colorado and Montana requirements, even for a personal project, as a future-proofing step.
  3. One-tap deletion of neural data and derived journal annotations.
  4. A claims policy: no diagnosis or treatment claims, and no "the device knows how you feel" language; use "markers" and "estimates" with confidence.
  5. A placebo-aware framing. The Wexler and Thibault critique suggests much of neurofeedback's benefit may be expectation-driven, so the product should stress self-reflection and habit change, which do not depend on the neural metric being highly valid.
- Feature idea **[Extrapolated]**: a "neuro-hype linter" in the LLM's output layer. A rule-based or classifier pass flags language that implies mind-reading, diagnosis or causal claims, and rewrites it into hedged, observational wording before it reaches the user.
- Feature idea **[Speculative]**: a "data dignity" dashboard showing exactly what neural data exists, where it is, what the LLM has said about it, and a per-insight "forget this" control.
- Risk to monitor: users may defer to device numbers over their own experience. Always eliciting self-report first and showing disagreements (Q3) is the mitigation.

### Gaps
- Did not verify any FTC enforcement action specifically against an EEG wearable company (2024–2026); none surfaced in searches.
- Did not verify the status of a proposed US federal "MIND Act" or the UNESCO Recommendation on the Ethics of Neurotechnology (believed adopted in November 2025, prior knowledge only).
- Did not retrieve the NeuroRights Foundation's 2024 audit of consumer neurotech companies' privacy policies (prior knowledge suggests most companies reserved broad rights over neural data; unverified).
- Most hype critiques found date from 2018–2019. A 2025–2026 independent validation review of Muse or Athena fNIRS metrics was not found.
