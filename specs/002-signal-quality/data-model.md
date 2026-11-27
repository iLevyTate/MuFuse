# Data Model: Signal Quality

Nothing here is stored, except the cue markers of a labelled session. Every other entity is computed from the raw
recording each time it is asked for. Exact rules: [contracts/quality-rules.md](./contracts/quality-rules.md).

| Entity | Fields | Rules |
|---|---|---|
| Rules | version ("1"), every limit of `contracts/quality-rules.md` | Frozen dataclass. A change that alters any answer raises `version`. |
| Stretch | start, end (seconds, timestamps of the EEG stream) | 256 EEG samples in a row. Never overlaps another. Never spans a gap. |
| ContactState | sensor, state (`good`, `settling`, `noisy`, `none`), reason (`flat`, `railed`, `hum`, `floating`, `loud`, or none), spread_uv, mains_share | One per sensor and stretch. `good` only from the third good stretch in a row. `noisy` and `none` always carry a reason. |
| Coverage | level (`full`, `reduced`, `one_forehead`, `none`), out (sensors that are not good) | From the four contact states. Only AF7 and AF8 decide between the three lower levels. |
| Blink | t (onset, seconds), duration_s | Found on AF7 and AF8 only. Two blinks are at least 0.8 s apart. Listed in time order. |
| Span | kind (`tension`, `movement`), start, end | Marked stretches in a row are one span. Start and end are stretch edges. A gap ends a span. |
| QualityAnswer | start, end, rules, contact (4 × ContactState), coverage, eye (`yes`, `no`, `unavailable`), tension (`yes`, `no`, `unavailable`), tension_uv (number or none), movement (`still`, `moving`, `unknown`), no_data (bool) | One per stretch. Derived: `disturbances`, `clean(sensor)`, `reasons(sensor)`. A no-data answer covers one gap; it has no contact states, and every sensor is not clean with the single reason `no_data`. |
| SessionQuality | rules, answers, blinks, tension spans, movement spans | The whole of one session, in time order. What `judge()` returns and what the golden file holds. |
| QualitySummary | rules; judged_s; no_data_s; per sensor: share good, settling, noisy, no contact, clean; coverage shares; blinks, blinks_per_min, blink_available_s; tension share; movement share, movement_unknown_s | Shares are over judged time, so time without data is left out of all of them. Blinks per minute are over the time the blink mark was available. A share with nothing to divide by is "not available", never 0. |
| Cue | t (seconds, same clock as the samples), kind (`blink`, `clench`, `turn`, `lift`, `down`, `quiet_open`, `quiet_closed`, `end`), sensor (for `lift` and `down`) | Stored as a system marker with the label `q:<kind>` or `q:<kind>:<sensor>`. Deleted with its recording. |
| ScoreReport | rules; allowed_s (2.0); per kind: found, total, pass; quiet: tension share, movement share, blinks per minute with eyes closed, false marks, pass; lifts: passed, total, pass; replay_identical (bool or "not checked"); overall pass | Holds numbers only: no signal, no device name, no path. A kind with no cues is "not scored", never passed. |

## Derived values of an answer

- `disturbances`: the stretch-level reasons, in this order: `eye`, `tension`, `movement`, then `eye_unavailable`,
  `tension_unavailable`, `movement_unknown`.
- `clean(sensor)`: the sensor's contact state is `good` and `disturbances` is empty.
- `reasons(sensor)`: empty when clean. Else the contact part (`settling`, or `noisy:<reason>`, or
  `none:<reason>`), if the state is not `good`, followed by `disturbances`.

## State rule: contact of one sensor

`(start or gap) → settling → settling → good`, one step per good stretch. A stretch graded noisy or no contact
shows that state at once and sets the count of good stretches back to zero. A gap sets it back to zero too.

## What reads what

`recording.LoadedSession` or live `Chunk`s → `QualityEngine` → `QualityAnswer`s and `Blink`s → `SessionQuality` →
`QualitySummary` (inspect), the live view, `ScoreReport` (with the cue markers), and later features (003, 005, 006).
