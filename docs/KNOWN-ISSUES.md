# Known issues

Open problems that change what MuFuse can be trusted for today. Remove an entry when it is fixed.

## Ear sensors (TP9, TP10) do not hold contact

**Status:** open since 2026-11-26. Tracked in issue #12. The cause is not known yet: it may be
the fit, the skin contact or the pads of this headband.

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

### What this blocks

| Affected | Effect |
|---|---|
| P0, the preflight fit check | Fails. It needs all four sensors good in 80% of windows or more. It is not loosened. |
| H8, the electrode check | Cannot be judged. It lifts the left ear sensor and reads the jaw clench on the ear sensors. |
| Live view | Shows FITTING instead of READY and names the ear sensor. This is correct. |
| Anything computed from TP9 or TP10 | Not trustworthy: rhythms at the ear sites, the jaw-clench signal, left against right. |

Every other hardware check of feature 001 has passed and does not depend on ear contact:
H1/H2, H3, H4, H5, H6, H7 and F1.

### How to work until it is fixed

- Recordings still hold all four EEG channels. Keep recording; nothing needs to be thrown away.
- Draw no conclusion from TP9 or TP10. Use AF7, AF8, the optics and the motion sensors.
- Feature 002 (signal quality) must mark each channel as usable or not for every stretch of a
  recording, and later features must use only the usable channels. They must still work when
  only the two forehead sensors are usable.
- A version of H8 on the right ear was considered and not built, because TP10 is not reliable
  either.
- To run the checks that do not need ear contact:

  ```
  uv run python scripts/hw_acceptance.py H6 H7 H5 F1 H4
  ```

### What to try

- Wipe all four sensors with a damp tissue. No alcohol and no scrubbing.
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

Then close issue #12 and remove this entry.
