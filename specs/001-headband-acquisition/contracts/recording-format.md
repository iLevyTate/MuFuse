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
`notes`, `software_version`, `device` {name, address, preset, driver, firmware, extra}, `streams` {kind: {file, columns,
sampling_rate, units}}, `completeness` {kind: {expected, received}} (null until finalized).

`device.firmware` is the headband's reply to the "v6" version query (`fw` field), or null when it could not be read.
`device.extra` holds the reply's stable fields when present (`hw`, `bn`, `bl`, `sp`, `tp`, `pv`), all strings.

Readers MUST: derive rows = filesize // (8 × len(columns)); ignore a trailing partial row; treat `ended_at: null` as an
unfinalized (crashed) session that is still valid.
