# Contract: CLI additions

Commands of feature 001 keep their behaviour and exit codes (`specs/001-acquisition/contracts/cli.md`).

| Command | Behavior | Exit codes |
|---|---|---|
| `mufuse stream`, `mufuse record` | The sensor panel reads the quality engine. Under it, one quality block (below). No new option. | unchanged |
| `mufuse inspect PATH` | After its present output, the quality summary (below). Works on any recording of format 1, including those made before this feature; the recording is not changed. | unchanged |
| `mufuse quality label [--source athena\|sim] [--device NAME] [--out DIR] [--no-check]` | Checks the fit first (AF7, AF8 good and motion flowing; after 60 s `s` starts anyway, `q` stops; kept as a `check:` marker), then records one guided labelled session (`labelled-session.md`) and prints its score report and the replay check. `--source sim` plays a scripted wearer that follows the cues. | 0 recorded (whatever the score), 4 connect failed, 5 cannot write, 130 stopped with Ctrl+C |
| `mufuse quality score PATH` | Scores a labelled session and prints the score report. | 0 pass, 1 gate not met, 2 no cue markers in the session, 6 unreadable |
| `mufuse quality score --public DIR` | Scores the cued blinks and jaw clenches of the public Muse 2 set unpacked in `DIR`. | 0 pass, 1 gate not met or not scored, 2 `DIR` is not the set |
| `python scripts/fetch_muse2_set.py [--dest DIR] [--from FILE]` | Downloads `sourcedata.zip` of the public set (or takes `FILE`), checks it against the published checksum, unpacks it into `DIR` (default: the user's cache folder, outside the repo) and prints the folder. The only network access of this feature; it sends nothing but the download request. | 0 ready, 1 download refused or checksum wrong |

## Live quality block

Updated once per judged stretch, so nothing flips more often than once a second.

```text
Coverage  reduced: forehead sensors good · TP9 is not touching skin (mostly mains hum)
Signal    14 blinks · muscle activity in the signal · head movement
```

- Coverage line: `full`, `reduced: forehead sensors good`, `one forehead sensor`, or `none`, then one text per
  sensor that is out. When all four are without contact: `No sensor is touching skin. Is the headband on?` and no
  list of four faults.
- Signal line: the blink count since the start, or `blinks: not available`; `muscle activity in the signal` while
  the newest stretch has the tension mark; `head movement` while it has the movement mark; `movement: unknown`
  when motion data is missing.
- Sensor texts, the complete list:

| State | Text |
|---|---|
| settling | `AF7 is settling` |
| noisy, loud | `AF7 is touching but noisy` |
| none, hum | `AF7 is not touching skin (mostly mains hum)` |
| none, railed | `AF7 is at the limit of its range` |
| none, flat | `AF7 gives a flat signal` |
| none, floating | `AF7 is not connected` |

- Colours: the three signal-quality tokens of `docs/BRAND.md`. They are used on sensor names and on the coverage
  word only.
- Every text names a sensor or a signal. None names a state of the person; tension is always "muscle activity in
  the signal".

## Quality summary in `inspect`

```text
Signal quality (rules 1)
  judged 58:12 · no data 0:48
  sensor   good  settling  noisy  no contact  clean
  TP9        0%        0%     3%         97%     0%
  AF7       96%        1%     2%          1%    81%
  AF8       97%        1%     1%          1%    82%
  TP10      94%        1%     4%          1%    79%
  coverage  full 0% · reduced 93% · one forehead sensor 5% · none 2%
  blinks    612 (10.9 per minute over 56:03)
  marked    muscle activity 4% · head movement 6% · movement unknown 0:00
```

A value with nothing to measure is printed as `not available`, never as 0.

## Score report

```text
Labelled session score (rules 1, a mark counts within 2.0 s of its cue)
  blinks        19 of 20   pass
  jaw clenches  18 of 20   pass
  head turns    20 of 20   pass
  quiet         muscle activity 1.8% · head movement 0.0% · 0.0 blinks per minute, eyes closed   pass
  lifts         10 of 10   pass
  false marks   2 in quiet stretches
  replay        identical to live
  RESULT        pass
```

The limits are those of the spec: 90% per kind, 5% and 5% and 2 per minute in quiet stretches, 9 of 10 lifts. The
report holds numbers only and may be shared; the recording may not.
