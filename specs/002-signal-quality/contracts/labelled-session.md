# Contract: Labelled session

One guided session of 9 minutes 25 seconds. The cue is the label. The same cue list drives the screen, the
markers, the scripted wearer of the rehearsal, and the scorer.

## Schedule

Times are seconds after streaming starts.

| From | To | Block | Cues |
|---|---|---|---|
| 0 | 20 | Settle: sit still, check the sensor panel | none |
| 20 | 80 | Quiet, eyes open | `q:quiet_open` at 20 |
| 80 | 140 | Quiet, eyes closed (the terminal bell ends it) | `q:quiet_closed` at 80 |
| 150 | 230 | 20 blinks, one every 4 s | `q:blink` at 150, 154, … 226 |
| 240 | 340 | 20 jaw clenches of about 1 s, one every 5 s | `q:clench` at 240, 245, … 335 |
| 350 | 450 | 20 head turns (to one side and back), one every 5 s | `q:turn` at 350, 355, … 445 |
| 460 | 560 | 10 lifts of a forehead sensor for 5 s, one every 10 s, AF7 and AF8 in turn | `q:lift:AF7` at 460, `q:down:AF7` at 465, `q:lift:AF8` at 470, … |
| 565 | | End | `q:end` |

Between blocks there are 10 s to read the next instruction. Within a block the screen counts ("Blink 7 of 20").

## Storage

Each cue is one line in the recording's `markers.jsonl`, written at its scheduled time:

```json
{"t": 1795700000.0, "kind": "system", "label": "q:blink", "source": "system"}
```

No other file is added. A session is a labelled session when it holds `q:` markers; it is complete when it holds
`q:end`. Deleting the recording deletes its cues.

## Scoring

All times are compared on the timestamps of the recording. "Allowed time" is 2.0 s.

- **Blink**: found when a blink's time lies from the cue to the cue + 2.0 s. A blink counts for one cue only.
- **Jaw clench**: found when a tension span starts at or after the start of the stretch that contains the cue,
  and no later than the cue + 2.0 s. A span that started earlier does not count.
- **Head turn**: the same with a movement span.
- **Quiet**: the stretches that lie fully between the cue + 3 s and the block end − 1 s. Share of them with the
  tension mark; share with the movement mark; for eyes closed, blinks per minute. Stretches whose mark is
  `unavailable` or `unknown` are left out of a share; when more than 10% of the quiet stretches are left out, quiet
  is "not scored".
- **False marks**: tension spans and movement spans that start in a quiet stretch, plus blinks in the eyes-closed
  quiet stretches.
- **Lift**: let T be the start of the first stretch, beginning at or after the `q:lift` cue, in which the sensor is
  not good. The lift passes when T is no later than the cue + 4 s, a stretch in which the sensor is without
  contact ends no later than T + 2.0 s, and the sensor is not noisy for more than two stretches in a row before
  its `q:down` cue.
- **Replay** (`mufuse quality label` only): the answers and blinks collected live equal those of `judge()` on the
  recording just written.

A kind passes with at least 90% found (18 of 20), quiet with at most 5% tension, 5% movement and 2 blinks per
minute, lifts with 9 of 10. The result is a pass when every scored part passes and nothing is "not scored".

## Why a stretch, not a sample, for clenches and turns

Tension and movement are judged once per stretch, so their spans begin on a stretch edge, up to one second before
the muscle or the head moved. The rule "the stretch that contains the cue, or up to 2 s after the cue" is the
spec's "within 2 seconds after its cue" at that resolution. Blink times are exact to the sample and use the spec's
rule as written.

## Public set

`mufuse quality score --public DIR` applies the blink and jaw-clench rules to the Muse 2 recordings of the public
set, with the set's own cue times as labels. Head movements are not scored. If the cue times cannot be read from
the files, the result is "not scored" with the reason.
