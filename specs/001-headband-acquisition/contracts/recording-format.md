# Contract: MuFuse Session Recording Format v1

```
<recordings>/<session_id>/
  manifest.json      # written at start, rewritten atomically (tmp + replace) at finalize
  eeg.f64            # float64 LE, row-major, columns: t, TP9, AF7, AF8, TP10, AUX1..AUX4
  motion.f64         # t, ACC_X, ACC_Y, ACC_Z, GYRO_X, GYRO_Y, GYRO_Z
  optics.f64         # t, OPT1..OPTn (n = 4/8/16 by preset), BATTERY
  markers.jsonl      # {"t":…, "kind":…, "label":…, "source":…}
  gaps.jsonl         # {"stream":…, "start":…, "end":…, "reason":…}
```

manifest.json keys: `format_version` (=1), `session_id`, `started_at`, `ended_at` (null until finalized),
`notes`, `software_version`, `device` {name, address, preset, driver, firmware}, `streams` {kind: {file, columns,
sampling_rate, units}}, `completeness` {kind: {expected, received}} (null until finalized).

Optional key, added without a version change: `lost_subpackets` {kind: count}, the subpackets the headset sent that
never arrived, counted from the device's own subpacket counter over every connection of the session. On preset p1041
one subpacket carries 2 EEG, 3 motion or 1 optics sample(s). Written at finalize; absent in older sessions and in
unfinalized ones. Readers MUST treat a missing key as "not measured".

`gaps.jsonl`: `end` is null for a gap that was still open when the recording stopped.

Readers MUST: derive rows = filesize // (8 × len(columns)); ignore a trailing partial row; treat `ended_at: null` as an
unfinalized (crashed) session that is still valid.
