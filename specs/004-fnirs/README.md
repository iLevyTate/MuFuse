# 004 fNIRS pipeline (experimental) — design note

**Goal.** Turn the Athena's forehead optics into relative changes of oxygenated and deoxygenated
hemoglobin (ΔHbO, ΔHbR) per detector, and give the owner a guided protocol that checks whether
those changes move the expected way on their own head. Every hemoglobin number is **EXPERIMENTAL**
until that validation passes, and is labelled so wherever it is shown.

**Gate (ROADMAP).** Breath-hold, mental arithmetic and rest blocks show the expected HbO direction
and timing in ≥ 70% of blocks across 5 sessions. In CI: the Beer–Lambert maths (round trip, log
base), the filters, the scorer, and the protocol rehearsed end to end on the simulator. The five
headband sessions are the owner's (H-004 below) and do not block the features after this one.

## What it delivers

- `src/mufuse/fnirs/mbll.py`: modified Beer–Lambert law, constants, DPF, forward model.
- `src/mufuse/fnirs/pipeline.py`: a recorded session → ΔHbO / ΔHbR per detector, filtered, with the
  left-out samples counted, a signal quality index per detector, optional short-channel regression.
- `src/mufuse/fnirs/protocol.py`: the guided validation protocol (cues, guide, rehearsal wearer) and
  its scorer.
- `mufuse fnirs show <session> [--csv PATH] [--short-channel]`, `mufuse fnirs protocol --source
  athena|sim [--check/--no-check]`, `mufuse fnirs score <session>`. (`show` is a subcommand:
  a group argument would swallow the names `protocol` and `score`.)
- Hemodynamic responses in the simulator's scripted wearer (`Wearer.hemo`), empty by default.
- Golden output in `tests/data/fnirs_reference/` (`scripts/make_fnirs_reference.py`).

## Decisions (defaults taken; change them here first)

1. **Rows.** BrainFlow wire order: OPT1-4 red (660 nm), OPT5-8 ambient, OPT9-12 730 nm, OPT13-16
   850 nm, each group LI, RI, LO, RO (`acquisition/optics.py`; check F1 confirms it per unit).
   16-channel presets only (p1041, p1042); others give "not available". No ambient subtraction:
   the headset appears to do it already. Frames with too much light are left out, never repaired.
2. **Modified Beer–Lambert, one log base.** ΔOD = −log10(I/I0). Prahl extinction coefficients,
   base 10, cm⁻¹ M⁻¹: 730 nm HbO 390, HbR 1102.2; 850 nm HbO 1058, HbR 691.32. DPF from
   Scholkmann & Wolf 2013 at age 30 (configurable): 6.31 at 730 nm, 5.23 at 850 nm. Distances:
   outer detectors 3.0 cm, inner 1.0 cm, **estimates from the FCC photos**, configurable. A 2×2
   solve per detector gives ΔHbO and ΔHbR in µM, **relative only**: an error in distance or DPF
   scales every value. I0 is the mean of the first 30 s of used samples. Natural-log OD with
   base-10 ε would inflate everything by ln 10 ≈ 2.3 (a bug found in OpenMuse); a test guards it.
3. **Filtering.** Low-pass 0.2 Hz (removes the heartbeat) and high-pass 0.01 Hz (drift), Butterworth
   order 2, zero-phase (`sosfiltfilt`), offline only. Optics with a time gap over 0.25 s are split
   into pieces, each filtered on its own. Left-out samples (too much light, or in a second that 002
   judged as moving) are bridged by a straight line only so the filter can run, then set back to
   "not available"; how many were left out is reported. No motion correction is claimed.
4. **Signal quality index** per detector: minus the correlation of ΔHbO and ΔHbR over 10 s windows
   (HbO and HbR should move against each other; muse.js and OpenMuse practice), its median shown.
   Reported only, never used to hide data.
5. **Short-channel regression** (outer − β·inner per side and chromophore, least squares over the
   used samples): built, **off by default**, labelled "unverified geometry": the inner detectors
   (~0.7–1 cm) are longer than the 8.4 mm adult optimum, so they hold some brain signal too.
6. **Protocol** (`f:` cue markers, the 002 pre-flight check first): 20 s settle, 60 s rest
   (`f:rest`), 5 breath-holds (`f:hold`: breathe out, hold 20 s, recover 40 s), 5 blocks of mental
   arithmetic (`f:arith`: count down by 7 silently for 30 s, rest 30 s), `f:end`. About 11.7 min,
   eyes open throughout (no eyes-closed part, so no tone is needed).
7. **Scorer.** Per block, on the mean of the outer detectors (LO, RO; the longer path reaches the
   cortex): mean ΔHbO in the block window minus its mean in the 5 s before onset. Windows:
   breath-hold **15–35 s** after onset (forehead HbO dips for about 10 s and peaks at 25–30 s,
   Nguyen 2024, research doc §5; the 5–25 s window first proposed would catch the dip), arithmetic
   5–30 s. Expected direction: HbO up for both. **The arithmetic direction on the forehead is not
   universal**: medial frontal HbO can fall (Pfurtscheller 2010), and arithmetic raises heart rate
   and blood pressure, which the scalp shows too (Kirilina 2012). A session reports its share of
   blocks in the expected direction; ≥ 70% passes that session; the 5-session verdict is the owner's.
8. **Simulator.** `Wearer.hemo = ((start, end, ΔHbO µM), ...)` with ΔHbR = −0.3·ΔHbO and a 5 s
   raised-cosine onset and offset, applied through the forward model to the 730 and 850 nm rows at
   each detector's distance. Empty by default: the 001, 002 and 003 rehearsals and golden files do
   not change. A rehearsal wearer follows the protocol's cues (a guess, not physiology).
9. **Versioning.** `FNIRS_VERSION = "1"` on every output; golden output from the simulator.

No new runtime dependency (numpy, scipy).

## Constitution Check

I: offline, local files only. II: output is "ΔHbO … µM, relative, EXPERIMENTAL", never a state.
IV: every constant in one module, `FNIRS_VERSION` on every output, golden files, the log-base test.
VI: honest uncertainty: relative units, estimated distances, the experimental label, the
non-universal arithmetic direction. The ear sensors are not involved.

## Open questions

- The real inner and outer distances (a ruler on the band, or the Valsalva inner/outer ratio).
- Does breath-hold HbO rise within 35 s on this forehead, or only in recovery?
- Should the score use HbDiff (HbO − HbR), which is more robust to scale errors?

## Hardware check H-004 (owner, not a show stopper)

Five sittings on different days: headband on, Muse app closed,
`uv run mufuse fnirs protocol --source athena` (about 12 minutes, eyes open). Each prints its
share of blocks in the expected direction; the gate passes when the five together reach 70%.
Until then fNIRS stays experimental.

## Done

- [x] mbll: constants, DPF, solve, forward model, round trip, log-base guard
- [x] pipeline: rows, glare and movement left out, pieces at gaps, filters, SQI, short channel
- [x] simulator `hemo`, rehearsal wearer; 001-003 references unchanged
- [x] protocol guide, cue markers, scorer; rehearsed end to end on the fake clock
- [x] `mufuse fnirs show / protocol / score`; golden output and its script
- [x] docs: README, CLAUDE.md, ROADMAP, tests/hardware/README.md

## What was found while building

- The rehearsal (1 µM per hold, 0.6 µM per count, simulated) scores 10 of 10 blocks in the
  expected direction: holds +0.76 to +0.95 µM, counts about +0.53 µM after the band-pass.
- A wearer whose forehead does nothing reads within ±0.03 µM per block, so its share lands near
  half by chance (60% on the simulator): the 70% line needs real responses.
- The simulator's "light" state dims the LED rows without tripping `too_much_light`; glare is
  tested with saturated ambient rows instead.
- [ ] H-004: five sittings on the headband (owner)
