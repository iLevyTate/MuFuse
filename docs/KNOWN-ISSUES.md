# Known issues

Open problems that change what MuFuse can be trusted for today. Remove an entry when it is fixed.

## Ear sensors (TP9, TP10) do not hold contact reliably

**Status:** open since 2026-11-26. Tracked in issue #12. On 2026-11-27, after the sensors were
wiped and the headband charged, both ear sensors made good contact and P0 and H8 each passed
once, so the left pad is not faulty. The contact is still fragile: it took many attempts and the
right ear sensor kept dropping out. The cause is most likely the fit or the skin contact.

**Until this is fixed, treat TP9 (left ear) and TP10 (right ear) as unreliable.** The forehead
sensors (AF7, AF8), the optics (fNIRS, pulse) and the motion sensors are not affected.

### What was measured

Firmware 3.1.31, BrainFlow 5.24.0, preset p1041. A sensor without skin contact picks up mains
hum, so it reads loud and almost all of its signal sits at 60 Hz.

| When | TP9 (left ear) | AF7 | AF8 | TP10 (right ear) |
|---|---|---|---|---|
| Acceptance sitting, first attempt (spread while still, limit 75 µV) | 205 µV, about 100% hum | 30 µV | 25 µV | 134 µV, about 100% hum |
| The same after wetting the skin | 160 µV, 99% hum | 37 µV | 31 µV | 8 µV, good |
| 8-minute recorded fit check that evening (share of 2 s windows with good contact) | 3% | 89% | 77% | 53% |

- TP9 stayed without contact through six attempts and the whole fit check.
- TP10 comes and goes. In the fit check it was good for about three minutes and then lost again.
- The fit check includes adjusting the headband, so the forehead numbers are lower than in a
  still sitting.

After cleaning, on 2026-11-27, in one run of the acceptance sitting:

| Check | Result |
|---|---|
| P0 | Passed at the third attempt: all four sensors good in 100% of the still windows. |
| H8 | Passed at the twelfth attempt, 3 h 19 min after P0: the lift changed TP9 in 100% of windows, and the clench raised the spread 14.1 times on TP9 and 7.2 times on TP10. |

- The eleven failed H8 attempts had poor contact at rest, TP10 dropping out during the clench or
  the blinks, or very large blinks on AF7.
- In the labelled sittings of feature 002 that evening the ear sensors came and went again.

### What this blocks

| Affected | Effect |
|---|---|
| P0, the preflight fit check | Fails whenever an ear sensor is out. It needs all four sensors good in 80% of windows or more. It is not loosened. |
| H8, the electrode check | Cannot be judged unless TP9 is steady at rest. It lifts the left ear sensor and reads the jaw clench on the ear sensors. |
| Live view | Shows FITTING instead of READY and names the ear sensor. This is correct. |
| Anything computed from TP9 or TP10 | Not trustworthy: rhythms at the ear sites, the jaw-clench signal, left against right. |

Every other hardware check of feature 001 has passed and does not depend on ear contact:
H1/H2, H3, H4, H5, H6, H7 and F1. P0 and H8 have each passed once (above).

### How to work until it is fixed

- Recordings still hold all four EEG channels. Keep recording; nothing needs to be thrown away.
- Draw no conclusion from TP9 or TP10. Use AF7, AF8, the optics and the motion sensors.
- Feature 002 (signal quality) marks each channel as usable or not for every stretch of a
  recording, and later features must use only the usable channels. They must still work when
  only the two forehead sensors are usable.
- A version of H8 on the right ear was considered and not built, because TP10 is not reliable
  either.
- To run the checks that do not need ear contact:

  ```
  uv run python scripts/hw_acceptance.py H6 H7 H5 F1 H4
  ```

### What to try

- Wipe all four sensors with a damp tissue. No alcohol and no scrubbing. The passes of
  2026-11-27 came after this.
- Wet the skin behind both ears. Keep hair out from under the pads.
- Seat each ear pad on the bone just behind the ear. Take glasses off, or put them on over the
  band.
- Tighten or loosen the band and watch the live view (`uv run mufuse stream`) for 30 s.
- If TP9 still reads loud with mostly mains hum after all of this, note it in issue #12 as a
  possible fault of the left pad.

### Fixed when

P0 and H8 both pass in one sitting:

```
uv run python scripts/hw_acceptance.py P0 H8
```

Then close issue #12 and remove this entry. The two passes of 2026-11-27 were hours apart with
failed attempts between them, so the entry stays for now.

## Signal quality: what rules v1 finds, and what it does not find yet

**Status:** open since 2026-11-27 (feature 002). The quality rules
(`specs/002-signal-quality/contracts/quality-rules.md`) were checked on the headband, on the
public Muse 2 set and on the simulator, and frozen as rules version 1 on 2026-11-27. No limit
moved in that check (blink limit 4 robust spreads and 15 µV, tension 10 µV, gyroscope 20 deg/s,
accelerometer 0.05 g); the numbers are in `specs/002-signal-quality/research.md`, R13 and R17.
The sitting that decides the gate, one full labelled session recorded after the freeze, is still
to come.

### What was measured

Each cell is cues found of cues given. The target is 90% (9 of 10 for the lifts).

| Data | Blinks | Jaw clenches | Head turns | Sensor lifts |
|---|---|---|---|---|
| Simulator, rehearsed labelled session | 20 of 20 | 20 of 20 | 20 of 20 | 10 of 10 |
| Muse S Athena, first labelled sitting (one person, before the freeze, same limits) | 19 of 20 | 20 of 20 | 18 of 20 | 9 of 10 |
| Public Muse 2 set (Lee and Ahn), forehead sensors only | 367 of 520 (70.6%) | 118 of 520 (22.7%) | not in the set | not in the set |

- The quiet minutes of that first sitting failed: the eyes were opened during the eyes-closed
  minute, because the bell that ends it made no sound. The fail is kept as recorded. The cue now
  also plays a tone, and the eyes-closed minute repeated alone passed (no blink, no muscle
  activity, no movement marked in 55 stretches).
- Every miss of that sitting is at the start of its block.

### What it does not do yet

- **The public set is below the target, and that is reported as a fail.** No blink or tension
  limit that was tried reaches 90% there (best: 82.9% of the blinks, 34.6% of the clenches), and
  the values that gain most there mark quiet signal on the Athena. In that set a jaw clench
  raises the forehead level to about 4.4 µV (rest 2.3), under the 10 µV limit. The ear sensors
  see it clearly (about 12 µV), but nothing may depend on them (above). A limit against a
  personal baseline is feature 003.
- **Natural blinks may not be marked.** In the eyes-open minute no blink was marked at any floor
  from 10 µV up. The mark finds deliberate blinks; do not read the blink count as a blink rate.
- **A hard, deliberate blink also gets the muscle mark.** It raises the tension level to about
  18 µV. That is real muscle work in the signal.
- **A jaw clench can come close to the movement limit.** One reached 19.9 deg/s against 20.
- After a large blink the 1-10 Hz filter swings back about 0.7 s later. The 0.8 s rule keeps
  that from counting as a second blink, with little margin (research R5).
- **The limits were checked on one person and one headband.** Run the labelled session on your
  own head before relying on the marks.

### How to work with it

- Contact and coverage are ready to use.
- Muscle activity and head movement mark clear events; the blink mark finds deliberate blinks.
- To score the rules on your own head (9.5 minutes, the ear sensors are not needed):

  ```
  uv run mufuse quality label --source athena
  ```

  A score under 90% is a finding, not a mistake of yours. The limits are not lowered for it; a
  change to them is a new rules version.

### Closed when

The gate sitting passes, for the first line of the status. The public set and the natural blinks
stay open until a later rules version finds them.
