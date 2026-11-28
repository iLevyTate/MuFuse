# 003 EEG and pulse features — design note

**Goal.** Turn judged signal into a small set of numbers per second that later features read: the
forehead spectrum (aperiodic exponent, alpha peak, band shares), blink rate, heart rate and
pulse-based variability (RMSSD), each with a z-score against the wearer's own rolling baseline.

**Gate (ROADMAP).** Reference outputs frozen as golden files; heart rate within ±3 bpm of a
reference. In CI the reference is the simulator's known heart rate; the chest-strap comparison is a
hardware check for the owner (H-003 below) and does not block the features after this one.

## What it delivers

- `src/mufuse/features/`: `params.py` (every constant, `FEATURES_VERSION`), `spectrum.py`,
  `pulse.py`, `baseline.py`, `engine.py` (`FeatureEngine`, `extract(session)`).
- `mufuse features <session> [--csv PATH]`: a per-series summary (median, spread, share of
  seconds available) and, if asked, one CSV row per second with the versions that made it.
- A `resting` EEG profile in the simulator: a 1/f background with alpha bursts, and a wearer
  heart rate, so spectral features can be tested. The 001 and 002 rehearsals do not change.
- Golden files in `tests/data/features_reference/`, rebuilt only by
  `scripts/make_features_reference.py` together with a raised `FEATURES_VERSION`.

## Decisions (defaults taken; change them here first)

1. **Clean data only.** A forehead channel's second counts only when 002 judged it `good` and the
   stretch has no eye mark, no tension and no movement. Ears are never read (#12).
2. **Spectrum.** Each counted second is paired with the second before it (2 s, 512 samples, Hann,
   0.5 Hz bins); a frame averages the pairs of the last 8 s and needs at least 2. Fewer: the
   spectral features are "not available" for that second, never guessed.
3. **Aperiodic exponent** by our own censored regression: a straight line fitted to log10 power
   against log10 frequency over 2–40 Hz, the 7–14 Hz alpha range left out. No fooof (deprecated,
   blocks Python 3.15). Exponent = −slope; r² kept so a poor fit can be seen.
4. **Alpha peak.** The largest residual above that line within 7–14 Hz; a peak only if it stands
   at least 0.1 log10 units (about 26%) above the line. "No peak" is a normal answer on the
   forehead (about half of eyes-closed Muse sessions show none).
5. **Band shares.** Theta 4–8, alpha 8–13, beta 13–30 Hz, as shares of 2–40 Hz power.
6. **Blink rate.** 002's blinks in the last 60 s, per minute, only when the eye mark was available
   through that minute.
7. **Pulse.** The last 10 s of optics, no frame with too much light and no movement in it. Every
   LED row with a clear heartbeat (`pulse_share` ≥ 0.5) is band-passed 0.6–3.5 Hz, scaled, turned
   to match the clearest one and averaged; beats are
   peaks at least 0.33 s apart, refined to sub-sample time by a parabola (64 Hz rounding adds about
   11 ms to successive differences otherwise). Intervals outside 0.33–1.5 s or 30% from their
   median are dropped. Heart rate = 60 / median interval; RMSSD needs 5 intervals in a row.
8. **Baseline.** Per series, the median and 1.4826 × MAD of up to the last 30 minutes of available
   values, before the current one is added; a z-score needs 60 values. MAD of zero: no z-score.
9. **Versioning.** Every frame carries `FEATURES_VERSION` and the quality `RULES_VERSION`.
10. **Same live and replayed.** The engine reads chunks only, through its own quality engine, so a
    recording gives the same frames however it is delivered.

## Constitution Check

- I, local-first: nothing leaves the machine. III, describe don't diagnose: output is numbers and
  "vs your baseline"; no state words. IV, versioned and regression-tested: decisions 9 and the
  golden files. VI, honest uncertainty: "not available" and "no peak" are answers. No new runtime
  dependency (numpy, scipy only).

## Open questions

- Where does the Athena's forehead noise floor start, so where must the fit end (40 Hz is a guess)?
- Is RMSSD at 64 Hz good enough, or should 009 use the peak-to-trough swing?
- Does the owner have a BLE chest strap for H-003?

## Hardware check H-003 (owner, not a show stopper)

Headband and a chest strap (or a phone camera HR app) at the same time, 5 minutes seated.
`uv run mufuse record --source athena --duration 300`, then `uv run mufuse features <session>`;
note the reference heart rate every minute. Pass: each minute's median within ±3 bpm.

## Done

- [x] spectrum, aperiodic fit, alpha peak, band shares — unit tests on known synthetic spectra
- [x] pulse beats, heart rate, RMSSD — unit tests on known beat trains and the simulator
- [x] rolling baseline and z-scores
- [x] `FeatureEngine` live = `extract` replayed; simulator `resting` wearer (`MUFUSE_SIM_WEARER=resting`)
- [x] `mufuse features` command; golden files and their script
- [x] docs: README command table, CLAUDE.md architecture, ROADMAP status
- [ ] H-003 on the headband (owner; not a show stopper)

## What was found while building

- On the simulator (exponents 1.0 / 1.5 / 2.0; 55 / 72 / 100 bpm) the exponent is found within 0.1
  and every heart-rate second within ±3 bpm (CI test `test_features_engine.py`).
- **RMSSD reads high.** The simulated pulse has no variability at all, yet RMSSD reads about
  25–75 ms. Its rows carry the heartbeat at about the signal-to-noise of a real Athena row (pulse
  share 0.6–0.9), and at that level each beat's time moves by tens of milliseconds. Averaging every
  row that shows a pulse (decision 7, `combined`) halved the error; timing beats on the upstroke
  instead of the top made it worse on this sine-shaped pulse and was dropped. RMSSD is shown as
  experimental; 009 should consider the peak-to-trough swing of the beat interval instead.
