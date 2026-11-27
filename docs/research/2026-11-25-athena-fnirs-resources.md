# Muse S Athena optics / fNIRS: resources for a raw-optics → HbO/HbR pipeline

Date: 2026-11-25. Scope: every public resource found on the Athena's optical sensors, decoders, existing HbO/HbR code, the methods we need, and validation paradigms.

**Legend**
- **VERIFIED (official):** stated by InteraXon/Muse.
- **VERIFIED (code):** read directly in source code during this session.
- **CONSISTENT (community):** two or more independent reverse-engineering sources agree, but InteraXon has not confirmed it.
- **UNVERIFIED:** a single source, no stated provenance, or contradicted elsewhere.
- **UNKNOWN:** not found anywhere.

**Bottom line**
1. InteraXon publishes only "5 optodes, bilateral frontal, 64 Hz, 20-bit" and PPG wavelengths of 850/730/660 nm.
2. Everything about geometry and channel order comes from community sources, and those sources conflict on the Optics16 channel order for firmware 3.1.19.
3. No source–detector distance has been published or measured by anyone with a stated method.
4. No validated open Athena HbO/HbR pipeline exists.
5. We must validate channel identity and geometry on our own unit before trusting any HbO/HbR number.

## Update 2026-11-26: channel order resolved (A vs B are two layers, not rivals)

- **BrainFlow board 67 rows are B (wire order).** 1-based: OPT1-4 red (660 nm), OPT5-8 ambient,
  OPT9-12 730 nm, OPT13-16 850 nm; within each group LI, RI, LO, RO. BrainFlow's
  `get_optics_canonical_index` returns the wire index unchanged and
  `MUSE_ATHENA_OPTICS_SCALE_FACTOR` is 1.0, so values are raw counts. **VERIFIED (code).**
- **A is libMuse's reordered output** (what Mind Monitor shows). libMuse 8.0.9's `IXNOptics.h`
  defines OPTICS1-16 as order A in microamps (mirrored in a public repo, 2026-05-26).
  **VERIFIED (official header, via mirror).** A reorder table reported from the Android libMuse,
  `canonical[i] = wire[(10,11,14,15,8,9,12,13,2,3,6,7,0,1,4,5)[i]]`, maps B onto A exactly.
  **UNVERIFIED (claimed).**
- Independent measurements agree with B on the wire: JHees (fw 3.1.19; flashlight, darkness,
  band-pass filters; OpenMuse #24, 2026-06-03) and OpenMuse PR #31 "Fix Optics16 channel mapping"
  (2026-10-20, open). nijave reports the same order on fw 3.1.19, 3.1.23 and 3.1.29 (claimed).
  OpenMuse `main` still carries the old labels; its Jan 2026 correlation summary likely scored
  data against those labels.
- Consequence for MuFuse: treat BrainFlow rows as B. Detector grouping (flashlight) and breath-hold
  tests are no longer needed to settle order. Keep one cheap on-unit check: guided **F1**
  (`scripts/hw_acceptance.py F1`) confirms OPT5-8 go dark in darkness and carry no heartbeat on
  the head. Record firmware with sessions (BrainFlow only logs the `fw` status field at debug level).
- Still open: measured source-detector distances. The FCC filing 2ABZI-MS03 (grant 2025-03-05)
  is public and its internal photos label the optics flex PD_LOUTER1, PD_LINNER1, a central LED,
  PD_RINNER1, PD_ROUTER1 (see 2026-11-26-muse-docs-and-oss-survey.md); spacing from the photos is
  an estimate, not a measurement.

### Firmware and decoder changes (checked 2026-11-26)

- Newest firmware seen publicly: **3.1.29** (community reports, Oct 2026). No official firmware
  changelog was found; Muse's 2026 announcements are app features only. No new hardware revision
  of the MS-03 was found, so sensor placement is presumed unchanged. **UNVERIFIED beyond 3.1.29.**
- The one documented wire change: the status/battery packet moved from 0x98 (20 B) to 0x88
  (a fixed 20 B; an earlier 188-230 B figure came from a framing bug) around fw 3.1.18 (OpenMuse 0.1.8 changelog; Mind Monitor 2.4.3 "Athena firmware
  3.1.18 and greater"). EEG (256 Hz), optics (64 Hz, same wire order) and IMU are reported
  unchanged up to 3.1.29. OpenMuse #28/#32 is a decoder framing bug, not a firmware change.
- **BrainFlow 5.23.0 changed Athena EEG scaling** from 1650/4095 to 1450/16383 µV per count
  (about 4.5x smaller; brainflow #855) and centres EEG on zero (#856). Verified in
  `muse_athena_constants.h` at tags 5.22.2 vs 5.23.0/5.24.0. MuFuse requires `brainflow>=5.23`.
- MuFuse now records the headband firmware in every session manifest (`device.firmware`, read
  from BrainFlow's debug log of the `v6` status reply) and shows it in the CLI banner, so a
  firmware change on our unit is visible immediately; re-run F1 if it changes.

### Units when comparing with other tools (noted 2026-11-26)

- **Optics: BrainFlow reports raw counts; OpenMuse and Mind Monitor divide by 32768.** A level
  quoted from those tools is 32768 times smaller than the same level in a MuFuse session. The
  ambient channels that "dropped to ~10 in darkness" (§1.3, measured through OpenMuse) therefore
  read about 330 000 BrainFlow counts when dark (10 × 32768 = 327 680), not a level near zero.
  **VERIFIED (code)** for the two scale factors; that raw/32768 is microamps stays UNVERIFIED.
- **The ambient rows sit on that pedestal on the head as well.** In MuFuse's own recordings so
  far (one unit) OPT5-8 read near 338 000 counts whatever the light: worn, they read about the
  same as when covered, and room light adds to that level. So "ambient goes dark" cannot be
  judged as "falls towards zero" in BrainFlow counts. Guided check F1 looks for the rows whose
  covered level matches their on-head level (within 10%) and that rise by at least 1000 counts
  in room light. The acceptance report prints the level of all 16 rows per phase in counts, and
  gives the covered level of OPT5-8 divided by 32768 as well, for comparison with those tools.
- **EEG full scale is about ±725 µV since BrainFlow 5.23** (14-bit counts at 1450/16383 µV per
  count, centred on zero; see the scaling change above). A sensor off the skin saturates there,
  so a threshold above it can never be reached: the channel check's rail threshold of 1000 µV
  is one. The acceptance report says so under its calibration suggestions; the threshold itself
  is tuned in feature 002.

---

## 1. Hardware facts

### 1.1 Sensor summary

| Fact | Value | Status | Source |
|---|---|---|---|
| fNIRS optode count | "5-optode", bilateral frontal cortex hemodynamics | VERIFIED (official) | [choosemuse.com product page](https://choosemuse.com/products/muse-s-athena); [Muse blog: Athena vs S G2](https://choosemuse.com/blogs/news/athena-vs-muse-s-g2-the-biggest-brain-tech-upgrade-yet) |
| fNIRS sample rate / resolution | 64 Hz, 20-bit | VERIFIED (official) | product page (above) |
| PPG wavelengths | "Triple wavelength": IR 850 nm, near-IR 730 nm, red 660 nm; 64 Hz, 20-bit; purpose "heart rate and SpO₂" | VERIFIED (official) | product page (above); also quoted in [OpenMuse README](https://github.com/DominiqueMakowski/OpenMuse) |
| Are PPG and fNIRS the same optical hardware? | Muse lists them as two "sensors". The BLE stream carries only one optics stream (tags 0x34/0x35/0x36), so in practice they are the same raw channels. | UNVERIFIED (inference) | Decoders: [BrainFlow](https://github.com/brainflow-dev/brainflow/blob/master/src/board_controller/muse/muse_athena.cpp), [OpenMuse decode.py](https://github.com/DominiqueMakowski/OpenMuse/blob/main/OpenMuse/decode.py) |
| Wavelengths used for fNIRS | 730 + 850 nm (660 nm also present on every detector in 16-ch mode) | CONSISTENT (community) | [Mind Monitor FAQ](https://mind-monitor.com/FAQ.php) optics table; OpenMuse `decode.py` docstring ("NIR: 730nm", "IR: 850nm"); [Zenodo preprint v3](https://zenodo.org/records/23663601) |
| Green LED? | None mentioned for Athena. Mind Monitor lists "Green" only for the MS-01 PPG. | No evidence of green on Athena | Mind Monitor FAQ PPG footnote |
| Geometry | **1 source at the centre of the forehead, 2 detectors per side** (Left/Right × Inner/Outer) = 5 optodes | CONSISTENT (community) with the official "5 optodes" | Zenodo preprint (Maccallini, Oct 2026): "one source at the center of the forehead and two receivers per side"; Mind Monitor and OpenMuse use LO/LI/RI/RO labels |
| Source–detector separation | Inner ≈ **1 cm**, outer ≈ **3 cm** (one author's table, with no stated measurement method). OpenMuse and muse.js *assume* 3 cm for every channel. | **UNVERIFIED**. Not published by InteraXon. | Zenodo preprint Table 1; muse.js [docs/fnirs.md](https://github.com/Polobase/muse.js/blob/HEAD/docs/fnirs.md) says "The source–detector separation is not published" |
| Short-separation channel? | If inner ≈ 1 cm, the inner detectors are "short-ish". They are still longer than the 8.4 mm adult optimum (Brigadoi & Cooper 2015), so they will contain some brain signal. | UNVERIFIED | See §4.3 |
| Ambient channel | Every detector has an "Ambient" reading taken with the LEDs off (16-ch mode only) | CONSISTENT (community) | Mind Monitor FAQ; Zenodo preprint ("what the receivers record when the LEDs are all off") |
| Units of the 20-bit value | Mind Monitor reports optics as "microamps", range "0 - 32 µA". This matches raw/32768 (2²⁰/32768 = 32). BrainFlow and muse-lsl output **raw counts** (scale 1.0). OpenMuse and Mind Monitor output raw/32768. | UNVERIFIED (Mind Monitor claim only) | Mind Monitor FAQ; BrainFlow `MUSE_ATHENA_OPTICS_SCALE_FACTOR 1.0` ([muse_athena_constants.h](https://github.com/brainflow-dev/brainflow/blob/master/src/board_controller/muse/inc/muse_athena_constants.h)); OpenMuse `OPTICS_SCALE = 1.0 / 32768.0` |
| Effective sample rate | Nominal 64 Hz. Measured 62.7–64.2 Hz. (A claim that optical counter gaps are data lost on the headset came from a battery-packet framing bug in that decoder, corrected by muse.js; BrainFlow reads that packet correctly. Our 10-minute recording on 2026-11-26 lost 0 subpackets on every stream.) | VERIFIED (measured by others) | [OpenMuse validation summary](https://github.com/DominiqueMakowski/OpenMuse/blob/main/validation/new_firmware/summary.md); [muse-rs athena-protocol.md](https://github.com/eugenehp/muse-rs/blob/HEAD/docs/athena-protocol.md) ("optical [counter skips] a little more often" than EEG's ~1/140) |
| Placement | Forehead, in the front module above the eyebrows. OpenMuse claims inner = medial frontopolar (medial BA10) and outer = lateral frontopolar (lateral BA10). | Placement: VERIFIED (official, "frontal"). BA mapping: UNVERIFIED. | [IEEE Spectrum](https://spectrum.ieee.org/muse-headband) ("five light sensors for fNIRS measurements on the forehead"); OpenMuse `process.py` docstring |
| LED drive current / optical power | Unknown. BrainFlow: "does not document the exact optical emitter current". | UNKNOWN | [BrainFlow SupportedBoards.rst](https://github.com/brainflow-dev/brainflow/blob/master/docs/SupportedBoards.rst) |
| Detector type / ADC | Unknown | UNKNOWN | — |
| Interleaving (LED multiplexing) timing within a 64 Hz frame | Unknown | UNKNOWN | — |
| SpO₂ | Muse announced SpO₂ "rolling out for research partners" (June 2025). The algorithm is not public. | VERIFIED (official claim); method UNKNOWN | [BusinessWire 2025-06-03](https://www.businesswire.com/news/home/20250603051086/en) (search snippet only) |
| FCC filing | **Found (2026-11-26): [2ABZI-MS03](https://fccid.io/2ABZI-MS03), grant 2025-03-05.** Internal photos label the optics flex PD_LOUTER1, PD_LINNER1, LED, PD_RINNER1, PD_ROUTER1 and the EEG flex FR_R, DRL, REF, DRL, FR_L. | VERIFIED (official filing) | [External photos](https://fccid.io/2ABZI-MS03/External-Photos/External-Photos-8088091); spacing from photos is an estimate (inner about 0.7-1 cm, outer about 3 cm), not a measurement. |
| Teardown | None found | UNKNOWN | — |
| InteraXon fNIRS validation paper | None found. The Muse blog cites only general EEG+fNIRS literature (Aghajani 2022). IEEE Spectrum reports no fNIRS validation, and researchers there caution about "limited channels". | Not found | IEEE Spectrum; Muse blog |

### 1.2 Presets → optics channel count and power

Preset names are **hex**: the status reply `ps` reads 4129 = 0x1021 at power-up and 4165 = 0x1045 after `p1045` ([muse-rs](https://github.com/eugenehp/muse-rs/blob/HEAD/docs/athena-protocol.md), measured on fw 3.1.19). OpenMuse's "p4129" is therefore the power-up preset 0x1021 written in decimal.

| Preset | EEG | Optics | Power | Agreement |
|---|---|---|---|---|
| p1041 | 8 | 16 (tag 0x36) | low | BrainFlow docs, AbosaSzakal, muse-rs (count) agree. OpenMuse says "Red LED bright". |
| p1042 | 8 | 16 | high | BrainFlow, AbosaSzakal, muse-rs (count) |
| p1043 | 8 | 8 (0x35) | low | BrainFlow, AbosaSzakal, muse-rs. OpenMuse says "bright". |
| p1044 | 8 | 8 | high | BrainFlow, AbosaSzakal, muse-rs. OpenMuse says "dim". |
| p1045 | 8 | 4 (0x34) | low | BrainFlow, AbosaSzakal ("default in MindMonitor"), muse-rs |
| p1046 | 8 | 4 | high | BrainFlow, AbosaSzakal, muse-rs |
| p1034 | **4** (BrainFlow, muse-rs) vs **8** (OpenMuse) | 8 | high (BrainFlow) | Resolved 2026-11-26: 4 EEG, 8 optics, high power (Muse's own preset list); OpenMuse is wrong. |
| p1035 | 4 | 4 | low (BrainFlow) | BrainFlow, OpenMuse, muse-rs |
| p1031/1032, p1033, p1036, p1025–p102A | see muse-rs | 16/8/4 | n/a | muse-rs only (measured) |
| p20/p21/p50/p51/p60/p61 | 4 | none on Athena (OpenMuse; muse-rs for p21) | — | BrainFlow docs list "optics data" for p50/p51/p60/p61, but OpenMuse and muse-rs saw no optics |

- **Low vs high power:** the labels come from AbosaSzakal and BrainFlow docs. muse-rs: "What separates the two presets of a row is not visible in which tags arrive." The odd/even pairing (odd = low, even = high) holds in every listed pair. Status: **CONSISTENT (community), mechanism UNVERIFIED**. BrainFlow documents the expected tradeoff: high power gives larger values, a better chance with weak contact, more battery use, and more saturation risk.
- **Defaults:** BrainFlow and OpenMuse use `p1041` (16-ch, low). BrainFlow's default `other_info` is `preset=p1041;low_latency=true` (sends `L1`, which muse-rs reports is the indicator-LED-on command).
- **Recommendation:** use **p1041 or p1042 (16-ch)** for fNIRS. Under the consensus mapping, the 4/8-ch modes carry no ambient or 660 nm channels, so ambient subtraction is impossible in those modes.

### 1.3 What each optics channel is physically: two competing hypotheses

**Hypothesis A: Mind Monitor / OpenMuse order (consensus).** Mind Monitor columns are 1-based. BrainFlow ancillary rows 1–16 equal these numbers.

| 16-ch index (1-based) | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Detector | LO | RO | LO | RO | LI | RI | LI | RI | LO | RO | LO | RO | LI | RI | LI | RI |
| λ | 730 | 730 | 850 | 850 | 730 | 730 | 850 | 850 | 660 | 660 | AMB | AMB | 660 | 660 | AMB | AMB |

- 8-ch mode = indices 1–8 above.
- 4-ch mode = LI730, RI730, LI850, RI850. These are the inner detectors only.
- Sources: [Mind Monitor FAQ](https://mind-monitor.com/FAQ.php) ("Optics Footnote: Values table (MS-03 Athena only)"); OpenMuse `OPTICS_CHANNELS` and `_OPTICS_INDEXES = {4: (4,5,6,7)}`; mind-vault-lab README; Zenodo preprint Table 1 (built from Mind Monitor CSVs).
- Mind Monitor may use the official SDK, so its labels may be authoritative. We could not confirm this.

**Hypothesis B: JHees, fw 3.1.19, Optics16 only ([OpenMuse issue #24](https://github.com/DominiqueMakowski/OpenMuse/issues/24), 2026-02-21).** 0-based packet order:

- 0–3 = RED (LI, RI, LO, RO)
- 4–7 = AMB (LI, RI, LO, RO)
- 8–11 = 730 nm (LI, RI, LO, RO)
- 12–15 = 850 nm (LI, RI, LO, RO)

Evidence offered:
- Lighting or covering each photodiode individually with a phone flashlight grouped the channels by detector.
- Channels 4–7 tracked room light and dropped to ~10 in darkness.
- One channel per outer detector was very weak, attributed to 660 nm at the long path.
- In a breath-hold, the larger drop was assigned to 730 nm.
- The author later says band-pass-filter tests "were consistent with my initial findings" but did no physiological validation.
- Status: **UNVERIFIED, unresolved**. The issue is open with no maintainer response.

**Hypothesis C: muse-rs names channels 0–2 "ambient, infrared, red".** This is inherited from the Muse 2/S Classic PPG GATT characteristics (`273e000f/10/11`) in [protocol.rs](https://github.com/eugenehp/muse-rs/blob/HEAD/src/protocol.rs). It is not an Athena measurement. Channels 3–15 are named `opt3…opt15` because "their roles are not documented". Treat as **not evidence**.

OpenMuse's own cross-correlation data ([ANALYSIS_SUMMARY.md](https://github.com/DominiqueMakowski/OpenMuse/blob/main/validation/new_firmware/channels_identification2/ANALYSIS_SUMMARY.md), Jan 2026):
- Its labelled AMB channels correlate across two devices (+0.59) and between inner and outer (+0.90 to +0.99) on-head.
- Its labelled LI–RI NIR channels correlate 0.97–0.99.
- Its labelled IR outer-vs-inner channels correlate negatively (−0.35 to −0.72).

These numbers fit Hypothesis A. They do not rule out a firmware-dependent reorder.

---

## 2. Decoder & channel mapping

### 2.1 Packet format (VERIFIED (code) in BrainFlow and OpenMuse; CONSISTENT with muse-rs and AbosaSzakal)

- GATT service `0xFE8D`. Control characteristic `273e0001-…`. Data characteristics `273e0013-…` (and `273e0014-…` in BrainFlow).
- Packet header is 14 bytes:
  - `[0]` length
  - `[1]` packet counter
  - `[2..5]` device clock (u32 LE)
  - `[9]` first subpacket tag
  - `[10]` its per-sensor counter
- Subpackets follow, each `[tag][counter][3 unknown][payload]`.
- Optics payload: **20-bit unsigned, LSB-first, sample-major.**

| Tag | Channels | Samples/subpacket | Bytes |
|---|---|---|---|
| 0x34 | 4 | 3 | 30 |
| 0x35 | 8 | 2 | 40 |
| 0x36 | 16 | 1 | 40 |

- Other tags:
  - 0x11/0x12 EEG 4/8 (14-bit)
  - 0x47 IMU
  - 0x53 DRL/REF (2 ch × 6 samples at 32 Hz)
  - 0x88 battery + ~200 unknown bytes (new firmware; OpenMuse speculates "possibly processed signals")
  - 0x98 battery (old firmware)
- Device-clock interpretation: OpenMuse uses 256 kHz ticks. muse-rs says this "does not fit fw 3.1.19". **UNVERIFIED.**
- Docs: [AbosaSzakal/MuseAthenaDataformatParser](https://github.com/AbosaSzakal/MuseAthenaDataformatParser) (first public description); [muse-rs athena-protocol.md](https://github.com/eugenehp/muse-rs/blob/HEAD/docs/athena-protocol.md) (most rigorous, with "measured" tags, fw 3.1.19 hex fixture); [mind-vault-lab/muse-athena-protocol](https://github.com/mind-vault-lab/muse-athena-protocol).

### 2.2 BrainFlow (`MUSE_S_ATHENA_BOARD = 67`, PyPI 5.24.0, 2026-11-08)

Files:
- [src/board_controller/muse/muse_athena.cpp](https://github.com/brainflow-dev/brainflow/blob/master/src/board_controller/muse/muse_athena.cpp)
- [inc/muse_athena.h](https://github.com/brainflow-dev/brainflow/blob/master/src/board_controller/muse/inc/muse_athena.h)
- [inc/muse_athena_constants.h](https://github.com/brainflow-dev/brainflow/blob/master/src/board_controller/muse/inc/muse_athena_constants.h)
- [inc/muse_options.h](https://github.com/brainflow-dev/brainflow/blob/master/src/board_controller/muse/inc/muse_options.h) (valid presets: p20, p21, p50, p51, p60, p61, p1034, p1035, p1041–p1046, p4129)
- Board description: [brainflow_boards.cpp](https://github.com/brainflow-dev/brainflow/blob/master/src/board_controller/brainflow_boards.cpp) around line 1169

What the code does (VERIFIED (code)):
- **ANCILLARY_PRESET** ("MuseAthenaAnc", 64 Hz, 20 rows):
  - row 0 = `package_num` = `(packet_counter << 8) | subpacket_counter`. The low byte is the per-sensor counter, which can be used for gap detection.
  - rows **1–16 = optical channels**
  - row 17 = battery
  - row 18 = timestamp
  - row 19 = marker
- `get_optics_canonical_index(tag, ch)` returns `ch` unchanged for all three tags:
  - 4-ch data lands in rows 1–4.
  - 8-ch data lands in rows 1–8.
  - Unused rows stay **0.0**.
- **No channel labels, wavelengths, or ambient subtraction.** Values are raw 20-bit counts (`MUSE_ATHENA_OPTICS_SCALE_FACTOR 1.0`).
- Docs say: "MuseS Athena uses optics data for PPG, and BrainFlow exposes this data as optical channels instead of PPG channels."
- Timestamps are host arrival times spread across the samples of each subpacket (`get_sample_timestamp`).
- DEFAULT_PRESET: EEG at 256 Hz (TP9, AF7, AF8, TP10; aux channels go to "other" rows). AUXILIARY_PRESET: IMU at 52 Hz.
- Under Hypothesis A, BrainFlow rows map as:
  - 4-ch: row1 = LI730, row2 = RI730, row3 = LI850, row4 = RI850.
  - 16-ch: row r = Mind Monitor column r.

**Python examples.** Renamed from `muse_anthena_*` to `muse_athena_*` in PR [#833](https://github.com/brainflow-dev/brainflow/pull/833) (2026-05-17).

[python_package/examples/tests/muse_athena_record_optics.py](https://github.com/brainflow-dev/brainflow/blob/master/python_package/examples/tests/muse_athena_record_optics.py):
- Defaults: `other_info='preset=p1035;low_latency=true'` (4-ch low power, 4-ch EEG), 60 s.
- Connects, sleeps for the duration, and calls `get_board_data(preset=ANCILLARY_PRESET)`.
- Writes the raw ancillary matrix with `DataFilter.write_file` to `muse_athena_optics_recording.csv`.
- Prints:
  - sample count
  - timestamp duration and median-dt sampling rate against the expected 64 Hz
  - "active" optical rows (std > 1e-9)

[python_package/examples/tests/muse_athena_analyze_optics_pulse.py](https://github.com/brainflow-dev/brainflow/blob/master/python_package/examples/tests/muse_athena_analyze_optics_pulse.py) works offline on that CSV:
1. Builds a time axis from timestamps.
2. Discards the first 5 s.
3. Picks active rows.
4. Per row: interpolates NaNs, linearly detrends, and applies a 4th-order zero-phase Butterworth **band-pass of 0.7–3.5 Hz**.
5. Z-scores each row and **averages all rows** into one pulse signal.
6. Picks polarity (signal vs −signal) by a peak score (mean peak height − RR coefficient of variation).
7. Local-max peak detection with a 65th-percentile threshold and min distance from max BPM (40–180 BPM).
8. Reports BPM from the median RR and from the FFT spectral peak.
9. Saves raw, filtered, pulse and spectrum PNGs.

This is a **PPG/heart-rate demo only**. It has no wavelength separation, no ambient subtraction and no HbO/HbR.

Other examples: `muse_athena_save_all.py`, `muse_athena_ppg_plotjuggler.py` (EEG to PlotJuggler, despite the name), `muse_athena_eeg_p21.py`, `muse_athena_eeg_band_powers.py`.

### 2.3 OpenMuse (D. Makowski; no license shown; last push 2026-01-28)

[OpenMuse/decode.py](https://github.com/DominiqueMakowski/OpenMuse/blob/main/OpenMuse/decode.py):
- `OPTICS_CHANNELS` (canonical 16): `LO_NIR, RO_NIR, LO_IR, RO_IR, LI_NIR, RI_NIR, LI_IR, RI_IR, LO_RED, RO_RED, LO_AMB, RO_AMB, LI_RED, RI_RED, LI_AMB, RI_AMB`.
- NIR = 730 nm and IR = 850 nm per the docstring.
- 4-ch mode is named `LI_NIR, RI_NIR, LI_IR, RI_IR`. 8-ch mode uses the first 8 names.
- Scale is `1/32768`.
- The README preset table is "derived from the signature of the data packets… More presets could exist."
- The roadmap still lists "Validate fNIRS signal extraction method" and "Validate the best PPG signal extraction method".
- Maintainer on [issue #23](https://github.com/DominiqueMakowski/OpenMuse/issues/23): "the exact computation is still somewhat unclear & unvalidated… a recent firmware update… seems to have changed somewhat the behaviour of the Optics channels… the algorithm used by official Muse apps is not open."
- [Issue #27](https://github.com/DominiqueMakowski/OpenMuse/issues/27): optics flatline (all zero/padding) on some units even with p1041. This is an open failure mode to guard against.

### 2.4 muse-lsl (BSD-3, PyPI 2.5.3)

[muselsl/athena.py](https://github.com/alexandrebarachant/muse-lsl/blob/master/muselsl/athena.py) / [constants.py](https://github.com/alexandrebarachant/muse-lsl/blob/master/muselsl/constants.py):
- The `-o/--optics` flag ("Include optical (fNIRS) data (Muse S Athena only)") creates an LSL stream of type `PPG` with 16 channels named `OPT0…OPT15`, unit "a.u.", scale 1.0 (raw counts).
- `optics_canonical_index` maps **0x34 (4-ch) to slots 4–7**, 0x35 to 0–7 and 0x36 to 0–15. Unused slots are 0. This is the same slot convention as OpenMuse and Mind Monitor, but **different from BrainFlow, which puts 4-ch data in rows 1–4**.
- Default preset p1041. `-P/--preset`. `--model athena` forces the Athena protocol.

### 2.5 muse-rs (Rust, Apache-2.0, crate 0.2.4, 2026-11-17)

- [docs/athena-protocol.md](https://github.com/eugenehp/muse-rs/blob/HEAD/docs/athena-protocol.md) is the best protocol reference:
  - measured preset table
  - command/reply table (`v4`, `s`, `h`, `p…`, `dc001`, `L1`)
  - per-sensor counter gaps
  - DRL/REF decoding
  - fixture `tests/fixtures/athena_fw3.1.19_p1041.hex`
- Optical values are raw and unscaled. Channel naming is not authoritative (see Hypothesis C).

### 2.6 amused-py / amused (MIT)

- [Amused-EEG/amused-py](https://github.com/Amused-EEG/amused-py) identified the BLE protocol. A separate PyPI `amused` 1.0.2 points to github.com/nexon33/amused.
- Its `muse_fnirs_processor.py` assumes **850/950/660 nm** and SDS 3 cm with DPF 6. The 950 nm contradicts InteraXon's published 730 nm. It also uses simulated data in its demo. **Do not use it for wavelengths or constants.**

### 2.7 Other decoders and tools

- **Mind Monitor** (paid app): OSC `/muse/optics` with 4/8/16 floats; CSV `Optics1..16`; units "0 - 32 µA"; mapping per Hypothesis A. [FAQ](https://mind-monitor.com/FAQ.php).
- [Polobase/muse.js](https://github.com/Polobase/muse.js): TypeScript Athena decoder plus an `@musejs/research` mBLL (see §3).
- [LuanVanTran12395/muse-monitor](https://github.com/LuanVanTran12395/muse-monitor): PySide6 + BrainFlow monitor with an 18-line `core/fnirs.py` mBLL (two wavelengths, log10, low-pass, window-mean baseline).
- [13cohene/muse-s-athena-dashboard](https://github.com/13cohene/muse-s-athena-dashboard), [redtronguy/athena-bci](https://github.com/redtronguy/athena-bci): visualisation only, with no fNIRS code found.

---

## 3. Existing pipelines (raw optics → HbO/HbR)

None of these is validated against a reference device.

| Pipeline | Wavelengths & ε | OD | Distance / DPF | Ambient | Filter | Notes |
|---|---|---|---|---|---|---|
| **Zenodo preprint**, P. Maccallini. v1 2026-06-13 ([20677279](https://zenodo.org/records/20677279)), v2 2026-06-15 ([20705110](https://zenodo.org/records/20705110)), v3 2026-10-26 ([23663601](https://zenodo.org/records/23663601), "fNIRS 2.pdf"). CC BY 4.0, R. | 730/850. Prahl ε × ln(10) (HbO₂ 390 / Hb 1102.2 at 730; 1058 / 691.32 at 850, cm⁻¹M⁻¹) | natural log vs the **mean over all recordings** (resting state) | **Outer 3 cm, inner 1 cm** × Scholkmann–Wolf age/λ DPF | Says ambient "is subtracted" | none described | 2×2 solve per detector. Reports ΔHbT = ΔHbO+ΔHbR and ΔHbDiff = ΔHbO−ΔHbR. Input is Mind Monitor CSV. Script excerpts are in the PDF; no repository. v2 mentions 9-month n=1 correlation with a subjective cognition score. Notes ambient channels drift over a session. |
| **OpenMuse `preprocess_fnirs`** ([process.py](https://github.com/DominiqueMakowski/OpenMuse/blob/main/OpenMuse/process.py)) | 660/730/850 least squares; Prahl ε (cm⁻¹M⁻¹) | `-np.log(I/mean(I))` (natural log) | 3.0 cm (assumed, every detector), DPF 7.0 | yes, per detector | band-pass 0.01–0.1 Hz on ΔOD | Outputs `{pos}_HbO/HbR/HbDiff/SQI` in µM. SQI = −rolling corr(HbO, HbR) over 10 s. **Unit bug (VERIFIED (code)):** natural-log OD with base-10 ε inflates concentrations by ln10 ≈ 2.30×. No motion correction. Global-mean I₀. |
| **OpenMuse `preprocess_ppg`** (same file) | 730+850 at all 4 detectors (8 channels) | — | — | yes | band-pass 0.5–8 Hz | Per-channel SQI = pulse-band (0.6–4 Hz) power / total power (Welch). Fusion weighted by SQI². Output is **negated** (reflectance pulse appears as a trough). |
| **muse.js `modifiedBeerLambert`** ([docs/fnirs.md](https://github.com/Polobase/muse.js/blob/HEAD/docs/fnirs.md)) | 660/730/850, Prahl ε | log10(I₀/I) vs baseline window | 3 cm default ("not published"), DPF 7 | yes (AMB as reference) | — | Drops non-positive channels instead of clamping. Forward-model round-trip test. Same HbO−HbR anticorrelation SQI. On-head p1041 capture: SQI +0.30 to +0.95, σ 0.03–0.33 µM. States that output is "ΔµM (relative)" and cannot be absolute. Notes that short-separation regression is not possible without known geometry. |
| **muse-monitor `fnirs.mbll`** ([fnirs.py](https://github.com/LuanVanTran12395/muse-monitor/blob/HEAD/src/musemonitor/core/fnirs.py)) | 2 wavelengths (default 730/850) | log10 vs window mean | config constants | not shown | low-pass | Minimal. |
| **amused-py `FNIRSProcessor`** | 660/850/**950** (wrong) | log10 | 3 cm, DPF 6 | no | — | Also computes TSI. Not trustworthy. |
| **Muse app** (official) | unknown | unknown | unknown | unknown | unknown | Closed. Drives the "owl" mental-effort neurofeedback ([Muse blog](https://choosemuse.com/blogs/news/athena-vs-muse-s-g2-the-biggest-brain-tech-upgrade-yet)). |

Community and forum findings:
- [OpenMuse issues #16/#23/#24/#27](https://github.com/DominiqueMakowski/OpenMuse/issues) are the substantive public discussion.
- BrainFlow PR [#779](https://github.com/brainflow-dev/brainflow/pull/779) points to threads in OpenBrainTalk Slack (`C0104MWE5FU`) and NeuroTechX Slack (`C08PVFWH4`). Both need login and were not read.
- No relevant Reddit r/Muse threads surfaced in search.
- The Mind Monitor forums were not reachable.
- **No InteraXon-published Athena fNIRS validation** was found.
- OpenMuse's [validation/preprocessing/find_heartbeats.py](https://github.com/DominiqueMakowski/OpenMuse/blob/main/validation/preprocessing/find_heartbeats.py) uses optics PPG peaks and troughs to locate cardiac-field artefacts and HEPs in AF7/AF8. This is useful for PPG timing.

---

## 4. Methods & libraries

### 4.1 Modified Beer–Lambert law: implementation notes

- **Formula:** ΔOD(λ) = −log₁₀(I/I₀) = [ε_HbO(λ)ΔHbO + ε_HbR(λ)ΔHbR] · d · DPF(λ). Solve per detector, with 2×2 inversion for 730/850 or least squares with 660.
- **Pick one log base and stay consistent.** Prahl ε (cm⁻¹M⁻¹, [OMLC table](https://omlc.org/spectra/hemoglobin/summary.html)) are base-10. With natural-log OD, multiply ε by ln10. MNE does exactly this: `optical_density` uses `-ln(I/mean)` and `_load_absorption` returns `ε·0.2303`, with distances in metres and ×1e-3 → M (VERIFIED (code), [_beer_lambert_law.py](https://github.com/mne-tools/mne-python/blob/main/mne/preprocessing/nirs/_beer_lambert_law.py)).
- **Prahl ε values (cm⁻¹M⁻¹, HbO₂ / Hb):**
  - 660 nm: 319.6 / 3226.56
  - 730 nm: 390 / 1102.2
  - 850 nm: 1058 / 691.32
  - These are identical across the OpenMuse, muse.js and preprint code.
- **DPF:** use Scholkmann & Wolf 2013 (J Biomed Opt 18(10):105004, [doi:10.1117/1.JBO.18.10.105004](https://doi.org/10.1117/1.JBO.18.10.105004)): DPF = 223.3 + 0.05624·A^0.8493 − 5.723e-7·λ³ + 0.001245·λ² − 0.9025·λ.
  - Computed here, age 30: DPF(660) = 6.45, DPF(730) = 6.31, DPF(850) = 5.23.
  - This formula comes from ~3 cm frontal data and is not valid for a ~1 cm channel.
- **Absolute scale is not attainable.** Distance (unknown) and DPF both scale ΔHb linearly, so report relative ΔHb or ΔOD-based features. HbDiff (HbO−HbR) and the HbO/HbR anticorrelation are scale-robust within a session.
- **Order of steps:**
  1. Subtract ambient.
  2. Reject saturated, non-positive or flat channels. Watch the 20-bit ceiling; high-power presets saturate.
  3. Compute ΔOD against a rest baseline, not the global mean.
  4. Motion-correct on ΔOD.
  5. Filter.
  6. Apply mBLL.
  7. Apply short-separation or systemic regression.
- **MNE-Python 1.13.2:**
  - `mne.preprocessing.nirs.optical_density`
  - `beer_lambert_law(raw, ppf=6.0, *, sd_distances=None)`. `sd_distances` (new in 1.13) lets you pass distances without a montage. `ppf` can be per-wavelength (since 1.7). Uses `pinv`, so it accepts 3 wavelengths.
  - `temporal_derivative_distribution_repair`, `scalp_coupling_index`, `short_channels(info, threshold=0.01)`.
  - Channel names must follow `S1_D1 730` style with wavelengths in `info`. You need to build a RawArray with fNIRS channel types.

### 4.2 Libraries

| Library | Relevant API | License / version | Notes |
|---|---|---|---|
| [MNE-Python](https://mne.tools) | as above | BSD-3, 1.13.2 | Core containers and mBLL |
| [MNE-NIRS](https://mne.tools/mne-nirs/) | `signal_enhancement.short_channel_regression(raw, max_dist=0.01)`, `enhance_negative_correlation` (Cui 2010), `preprocessing.motion_correct_spline(raw, mask, smoothing=0.99)`, `motion_correct_wavelet(raw, iqr=1.5)`, `detect_motion_artifacts`, `peak_power`, `scalp_coupling_index_windowed`, `quantify_mayer_fooof`, GLM (`run_glm`, `make_first_level_design_matrix`) | BSD-3, 0.7.3 | VERIFIED (code) function names on main |
| [Cedalion](https://github.com/ibs-lab/cedalion) | `nirs.cw.int2od/od2conc/beer_lambert`; `sigproc.motion.tddr/motion_correct_spline/splineSG/PCA/wavelet`; `sigproc.quality.sci/psp/gvtd/snr/id_motion`; `sigproc.physio.ampd` (heartbeat peaks), `global_component_subtract`; GLM with short-separation support; example notebooks `examples/physio/71_ampd_heartbeat.ipynb` and `22_motion_artefacts_and_correction.ipynb` | MIT, 25.1.0 | xarray-based. Closest Python analogue to Homer3. |
| [Homer3](https://github.com/BUNPC/Homer3) | `hmrR_Intensity2OD`, `hmrR_MotionCorrectSpline`, `hmrR_MotionCorrectTDDR`, `hmrR_OD2Conc`, `hmrR_GLM` with short-separation regressors | MATLAB | Reference implementations. Function names from general knowledge, not checked this session. |
| [TDDR reference](https://github.com/frankfishburn/tddr) | MATLAB + Python | — | Fishburn et al. 2019, NeuroImage 184:171–179 ([PMC6230489](https://pmc.ncbi.nlm.nih.gov/articles/PMC6230489)). Apply to OD, not concentration. Parameter-free. |
| [NeuroKit2](https://github.com/neuropsychology/NeuroKit) | `ppg_clean`, `ppg_peaks`, `ppg_process`, `hrv` | MIT | PPG from the fused optics signal |

### 4.3 Short-separation regression (SSR)

- Brigadoi & Cooper 2015 (Neurophotonics 2(2):025005, [UCL PDF](https://discovery-pp.ucl.ac.uk/id/eprint/1482113/1/Brigadoi_2015_Neurophotonics_HowShortIsShort.pdf)): the optimum adult short-channel distance is **8.4 mm**, defined as 5% of the long channel's brain sensitivity.
- If the Athena inner detectors are ~10 mm, they are near this optimum but slightly long. Regressing them out of the outer (~30 mm) channels removes some true brain signal. Expect attenuated, not inflated, effects.
- Options:
  1. Per-side OLS or GLM nuisance regression of LO on LI (and RO on RI), done per wavelength in OD or per chromophore.
  2. A Kalman/state-space form (Gagnon et al. 2011/2014; not fetched this session).
  3. If geometry proves inner ≈ outer, fall back to global or systemic regressors: the mean of all detectors, the PPG envelope, IMU, Mayer-wave band (~0.1 Hz) and respiration.
- Tsubaki 2018 (Valsalva, [Neurophotonics 5(1):015002](https://pmc.ncbi.nlm.nih.gov/articles/PMC5786506)): MAP correlated r = 0.963 with the 15 mm HbO and 0.893 with the 30 mm HbO. Shallow channels carry more systemic signal, which supports SSR.
- Kirilina et al. 2012 ([PMC3348501](https://pmc.ncbi.nlm.nih.gov/articles/PMC3348501)): **task-evoked frontal fNIRS artefacts come from sympathetically driven scalp venous volume changes co-localised with scalp veins**. This is the dominant false-positive risk for a forehead-only device.
- Tachtsidis & Scholkmann 2016 ([PMC4807243](https://pmc.ncbi.nlm.nih.gov/articles/PMC4807243)): always report HbO **and** HbR. HbR is more robust to systemic signal but not immune.

### 4.4 Motion artefacts

- **TDDR** is the first choice: parameter-free, works on OD, available in MNE, Cedalion and the reference repo.
- **Spline** (Scholkmann et al. 2010, Physiol Meas 31:649; not fetched) needs an artefact mask, from MNE-NIRS `detect_motion_artifacts` / Cedalion `id_motion` **or from the Athena IMU (52 Hz)**.
- **Wavelet** (Molavi & Dumont 2012) is in MNE-NIRS and Cedalion.
- **Spline + SG** (Jahani 2018) is in Cedalion.
- Brigadoi et al. 2014 (NeuroImage) compared methods on real cognitive data and favoured wavelet and spline (not fetched).
- With only 2–4 detectors, PCA-based correction has almost no spatial redundancy. Prefer TDDR, IMU-gated spline and SQI-based rejection.

### 4.5 PPG from optics

- **BrainFlow example:** 0.7–3.5 Hz Butterworth band-pass, z-score, average all channels, polarity selection, peak detection.
- **OpenMuse `preprocess_ppg`:** ambient subtraction, 0.5–8 Hz band-pass, spectral SQI weighting, then negation.
- The cardiac pulsation is also a **coupling-quality index**. Use SCI (Pollonini et al. 2014/2016): the correlation of 730 and 850 nm band-passed 0.5–2.5 Hz at the same detector. Implementations: `mne.preprocessing.nirs.scalp_coupling_index`, Cedalion `quality.sci`. Also use PSP (peak spectral power) via MNE-NIRS `peak_power` and Cedalion `quality.psp`.
- Use the 730/850 pair on the **inner** detectors for heart rate (largest pulsatility in community reports). Use 660/850 for any SpO₂-style ratio of ratios. Muse's own SpO₂ calibration is not public.

---

## 5. Validation paradigms

The Athena sits over frontopolar cortex (BA10), not DLPFC. Responses in published DLPFC-centred studies will be weaker, or **opposite in sign**, at the Athena's sites. Where no source was opened, numbers below are marked approximate.

| Paradigm | Protocol | Expected response | Use for Athena |
|---|---|---|---|
| **Breath-hold** (hypercapnia, mostly systemic) | 15–40 s holds after a normal exhale, 60 s+ recovery, ×5. Blocked ~20 s holds have been used on PFC (e.g. [Molavi et al., BU](https://www.bumc.bu.edu/bergethonlab/files/2011/08/Neuroimage-J.pdf)). | Forehead CW-NIRS at 3/4 cm (Nguyen et al. 2024, [PMC11048477](https://pmc.ncbi.nlm.nih.gov/articles/PMC11048477)): HbO **dips at ~0–10 s**, crosses baseline at ~15–20 s and **peaks at ~25–30 s**. Mean breath-hold was 41 ± 22 s. Their reported amplitudes (~0.02 "µM") look implausibly small; check units before using as a magnitude reference. Other work: oxygenation rises mainly in recovery, HHb small. A boxcar fits poorly as CO₂ ramps. | **Sanity check of wavelength identity and sign.** HbO and HbT should rise late. 730 nm (HbR-weighted) and 850 nm should differ in ΔOD sign or magnitude (the JHees approach). It also tests the inner-vs-outer systemic ratio. |
| **Valsalva** | 15 s strain at ~40 mmHg, ×3–5, 60 s rest | Large systemic HbO/HbT swings following MAP phases. Shallow (15 mm) channels track MAP more (r 0.96) than deep (30 mm, r 0.89) (Tsubaki 2018, [PMC5786506](https://pmc.ncbi.nlm.nih.gov/articles/PMC5786506)). In healthy controls, HbO increment latency at 30 mm was 0.39 ± 0.23 s (Kim et al. 2018, Neurophotonics). | **Quantify inner vs outer superficial weighting.** This is the best empirical test of the 1 cm vs 3 cm geometry claim. |
| **Mental arithmetic** (serial subtraction) | 20–30 s task / 20–30 s rest, ×8–10 | Pfurtscheller et al. 2010 (Int J Psychophysiol 76:186–192; 52-ch, n=10): **HbO increase over DLPFC bilaterally, but a HbO decrease over medial anterior PFC**. HbR changes smaller and n.s. | Expect **negative or ambiguous HbO at inner (medial) detectors** and possibly positive at outer ones. This is a strong test for systemic confounds (arithmetic raises HR and BP). |
| **n-back** (0/1/2/3-back) | e.g. Fishburn et al. 2014 ([Front Hum Neurosci 8:76](https://www.frontiersin.org/articles/10.3389/fnhum.2014.00076/full)): 27 s blocks (9 × 3 s trials), 14 s fixation, 3 blocks per load | HbO **scales linearly with load** in bilateral PFC. HbR did not survive correction. Amplitudes not reported in text. Typical frontal task ΔHbO is ~0.1–1 µM, peaking ~5–8 s after block onset and plateauing within a block (approximate, general literature, not verified this session). | Primary workload paradigm. Compare 2/3-back vs 0-back. Expect a small effect at BA10. Confirm HbO↑ with HbR↓ (anticorrelation SQI). |
| **Verbal fluency** (phonemic) | Japanese clinical protocol: 30 s pre-baseline, 60 s task (3 × 20 s initial letters), 60–70 s post (e.g. [PMC5862477](https://pmc.ncbi.nlm.nih.gov/articles/PMC5862477)). Results reported as integral or centroid in mM·mm (no DPF). | HbO↑ / HbR↓ over lateral PFC and frontopolar regions in healthy adults ([PMC9120192](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9120192/)). Exact mM·mm magnitudes not extracted this session. | Robust frontopolar activator, but speech causes **jaw and temporalis motion**. Use the IMU to gate. Covert speech avoids this but gives a weaker response. |
| **Paced breathing at 6/min** | 3–5 min | Strong 0.1 Hz oscillation in all optics and HR | Checks that the pipeline preserves low-frequency content. Also a systemic-regressor test. |
| **Posture / head-down** | 1 min | Large superficial venous changes | Artefact characterisation only |

General guidance:
- Report HbO and HbR.
- Model systemic covariates: HR from PPG, IMU, respiration from optics or IMU.
- Use within-subject block averages with ≥8 repetitions.
- Follow the [Yücel et al. 2021 best-practices checklist](https://pmc.ncbi.nlm.nih.gov/articles/PMC7793571) (Neurophotonics 8(1):012101).
- A **reference device** (research fNIRS with short channels, or at least a chest ECG and finger PPG) is needed to claim validity.

---

## 6. Open questions (with proposed tests on our own unit)

1. **Optics16 channel order on our firmware: A (Mind Monitor/OpenMuse) vs B (JHees).** First query firmware with `v4`. Then run these tests:
   - Cover or illuminate each detector in turn to group channels by detector.
   - Darkness test: AMB channels drop to near zero and show no cardiac pulsatility.
   - View the emitter through a phone camera: 660 nm is visibly red and 850 nm is invisible to the eye.
   - Breath-hold ΔOD sign and size per wavelength.
   - If available, narrow band-pass filters at 660/730/850 nm.
2. **Source–detector distances.** No published or measured value exists. Measure optode centres directly on the headband pod with calipers or a macro photo, then calibrate against the Valsalva inner/outer response ratio. The FCC internal photos (2ABZI-MS03) show the layout but not distances.
3. **Is the inner pair usable as a short-separation regressor?** It is ~1 cm (claimed), longer than the 8.4 mm optimum.
4. **Low vs high power.** Is it only LED current? Does it change gain or integration time? Measure DC level, saturation headroom and pulsatile SNR in p1041 vs p1042.
5. **Do 4/8-ch modes really lack ambient?** Does p1045 (Mind Monitor default) use ambient-corrected values internally?
6. **Units.** Is raw/32768 really µA (Mind Monitor), and is the response linear?
7. **Firmware drift.** OpenMuse reports that a firmware update changed optics behaviour. Ambient channels drift over sessions (preprint). Record the firmware version with every session.
8. **0x88 payload** (~200 unknown bytes on new firmware). It might contain on-device processed optics or SpO₂. Not decoded anywhere.
9. **Optics flatline failure** (OpenMuse #27). Detect it and alert in the pipeline.
10. **Timing.** BrainFlow uses host timestamps. The device-clock interpretation is disputed (OpenMuse vs muse-rs). Packet gaps need NaN-filling via the per-sensor counter, which is the low byte of BrainFlow row 0.
11. **Official algorithm.** The Muse app's mental-effort/oxygenation algorithm and SpO₂ calibration are closed. No InteraXon validation paper exists.
12. **Slack threads** (OpenBrainTalk `C0104MWE5FU`, NeuroTechX `C08PVFWH4`). Not read (login required). They may hold InteraXon-adjacent knowledge.

### Implementation recommendations for MuFuse
- Record **p1041 (16-ch)** through BrainFlow ANCILLARY rows 1–16. Store raw counts plus firmware version, preset and `package_num`.
- Make the channel map a **versioned config** with Hypothesis A as default. Run the bench tests in Q1 before trusting it.
- Pipeline:
  1. Subtract ambient.
  2. Compute ΔOD (log10, rest baseline).
  3. TDDR, with IMU-gated spline as a fallback.
  4. Band-pass 0.01–0.2 Hz.
  5. mBLL with 730/850 nm (660 optional), using Scholkmann–Wolf DPF and a **parameterised distance**. Report relative ΔHb.
  6. Regress inner channels (or global and PPG nuisance signals) out of outer channels.
  7. Gate with SCI/PSP plus the HbO/HbR anticorrelation SQI.
- If you reuse the OpenMuse code, avoid its ln/log10 mismatch.

## Update 2026-11-26

- Units: Muse's own SDK definitions give optics in microamps; Mind Monitor's raw/32768 (0-32 µA)
  matches. BrainFlow still reports raw 20-bit counts.
- EEG full scale ±725 µV is confirmed by the official product page ("725 µV AC signal").
- In BrainFlow counts the ambient rows sit on a dark pedestal of about 338k on the head (the
  "about 10 in darkness" of raw/32768 above); covered they stay there, in room light they rise,
  and in bright light they reach the 20-bit ceiling while every LED row reads exactly 0. That
  zeroing suggests the headset already subtracts ambient light: never subtract it again.
- On the head every detector shows the heartbeat (the 0.7-3 Hz peak held 75-92% of the 0.3-8 Hz
  power over 10 s windows in a 10-minute recording); off the head it does not.
- F1 confirmed OPT5-8 as the ambient rows on firmware 3.1.31.
- Full survey and sources: [2026-11-26-muse-docs-and-oss-survey.md](2026-11-26-muse-docs-and-oss-survey.md).
