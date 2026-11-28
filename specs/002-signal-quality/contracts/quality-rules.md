# Contract: Quality rules, version 1

The definition a test or a port must reproduce. Frozen on 2026-11-27, before rules v1 was used for the gate
score: the limits for blinks, tension and movement were checked on real data and stand as drafted (research
R13). A change to anything on this page that alters an answer is rules v2.

Inputs: the EEG stream (256 Hz, µV, columns TP9, AF7, AF8, TP10) and the MOTION stream (52 Hz, ACC_X/Y/Z in g,
GYRO_X/Y/Z in deg/s), each with one timestamp per sample, as a source delivers them or a recording holds them.
No other input. No clock.

## 1 Stretches

1. The anchor is the first EEG sample, or the first EEG sample after a gap.
2. A gap is a step of more than 0.25 s between two consecutive EEG timestamps.
3. Counted from the anchor, every 256 EEG samples are one stretch. Its start is the timestamp of its first sample,
   its end is start + 1.0 s.
4. Samples between the last full stretch and a gap are not judged. One no-data answer covers the time from the end
   of the last full stretch to the first sample after the gap.
5. A stretch is judged when the EEG stream has delivered 64 samples past its last sample **and** the newest MOTION
   timestamp is at or past its end. If the second condition does not come true, it is judged when the newest EEG
   timestamp is at or past end + 1.0 s. Before a gap and at `finish()`, the stretches still waiting are judged with
   the samples that exist.
6. The MOTION samples of a stretch are those with start ≤ timestamp < end.

## 2 Contact (all four sensors)

Each sensor's 256 raw samples, not centred, are graded in this order (`grade_window` of feature 001):

| Test | Grade, reason |
|---|---|
| more than 10% of the samples at or beyond 710.5 µV in size (98% of 725 µV) | none, `railed` |
| robust spread (1.4826 × median absolute deviation) under 1 µV | none, `flat` |
| spread ≤ 75 µV, and standard deviation > 75 µV, and ≥ 60% of the power on the device pattern lines | none, `floating` |
| spread ≤ 75 µV | good |
| spread > 75 µV and mains share ≥ 60% | none, `hum` |
| spread > 75 µV | noisy, `loud` |

- Power: the sample mean is removed, a Hann window applied, then the squared size of the real FFT (1 Hz bins).
- Mains share: power within 1 Hz of 50 or 60 Hz, divided by all power at 1 Hz and above, with the bins within 1 Hz
  of 21.33, 42.67 and 64 Hz left out of both.
- Pattern lines: within 1 Hz of k × 21.33 Hz, k = 1 to 6, as a share of all power at 1 Hz and above.
- A stretch in which more than half of a sensor's samples are not finite numbers is none, `flat`.

State: `good` when this stretch and the two before it (with no gap between) are graded good; `settling` when this
stretch is graded good but that is not yet true; else the grade (`noisy`, `none`) with its reason.

Coverage: `full` when all four states are good; else `reduced` when AF7 and AF8 are good; else `one_forehead` when
one of them is good; else `none`. `out` lists the sensors whose state is not good, in the order TP9, AF7, AF8, TP10.

## 3 Forehead sensors in use

For sections 4 and 5, a forehead sensor (AF7, AF8) is in use in a stretch when its grade in that stretch is not
none. TP9 and TP10 are never read by sections 4, 5 and 6.

## 4 Eye mark and blinks

Per forehead sensor, sample by sample since the anchor:

1. Band-pass: `scipy.signal.butter(2, [1, 10], btype="bandpass", fs=256, output="sos")`, applied forward only,
   state zero at the anchor and carried across stretches.
2. Envelope: the absolute value, then the mean of the last 32 samples (samples before the anchor count as 0).
3. Limit of a stretch: from the envelope samples of the 30 s before the stretch start (not before the anchor),
   every 8th sample counted from the anchor: median + 4 × 1.4826 × median absolute deviation, and at least
   15 µV.

Then, for both sensors together:

4. A sample is "above" when the envelope of every sensor in use is above that sensor's limit for the stretch the
   sample lies in. With no sensor in use it is not above.
5. A run is a row of above samples with no break. An eye event is a run of 16 samples or more.
6. Eye mark of a stretch with first sample index `i`: `unavailable` in the first 5 stretches after an anchor and
   when no forehead sensor is in use; else `yes` when an eye event has a sample with index from `i − 32` to
   `i + 287`; else `no`.
7. A blink is an eye event of at most 307 samples (1.2 s). Its time is the timestamp of its first sample. A blink
   whose time is less than 0.8 s after the previous blink's time is dropped. Blinks are not reported from
   stretches whose eye mark is `unavailable`.

The envelope trails the eye by about 0.1 s; the blink time is not corrected for that.

Three readings that the steps above leave open, fixed here:

- The 64 samples after a stretch lie in the next stretch: they use that stretch's limits (known from the samples
  before it) and the sensors in use in the stretch being judged (the next one is not graded yet).
- A sample that is not a number is replaced, before the band-pass, by the mean of the numbers of its sensor in
  its stretch (0 when there are none); the same holds for section 5.
- "The previous blink" is the previous blink that was reported; a blink first sample decides its stretch for
  the `unavailable` rule.

## 5 Tension

Per forehead sensor in use and per stretch, with `x` the 256 samples minus their mean, `w = numpy.hanning(256)`
and `X = rfft(x * w)`:

- level = sqrt( Σ 2·|X[k]|² / (256 · Σ w²) ) over the bins k (in Hz) from 30 to 48 and from 66 to 98, without
  42, 43, 44, 84, 85 and 86. The unit is µV rms.
- Level of the stretch: the smaller of the two levels when both sensors are in use; the one level when one is.
- Tension mark: `unavailable` when no forehead sensor is in use (the level is then none); else `yes` when the
  level is above 10 µV; else `no`.

## 6 Movement

From the MOTION samples of the stretch:

- `unknown` with fewer than 26 samples.
- Else `moving` when sqrt(mean(GYRO_X² + GYRO_Y² + GYRO_Z²)) is above 20 deg/s, or the standard
  deviation of ACC_X, ACC_Y or ACC_Z is above 0.05 g.
- Else `still`.

The movement value applies to the EEG and to the optics of the same stretch.

## 7 Spans

Stretches in a row (no gap between) with tension `yes` are one tension span, from the start of the first to the
end of the last. The same for movement `moving`.

## 8 Clean

A sensor is clean in a stretch when its state is `good`, the eye mark is `no`, the tension mark is `no` and
movement is `still`. Everything else is not clean, with the reasons of `data-model.md`.

## 9 Tolerances for the reference recording

`tests/data/quality_reference/answers.json` must be reproduced with: equal stretch starts and ends (1e-9 s),
equal states, reasons, coverage, marks, spans and blink count; blink times within one sample (1/256 s);
`spread_uv`, `mains_share` and `tension_uv` within 1e-6 relative (1e-9 absolute near zero). The reference is built
so that no measured value lies within 5% of its limit.
