# Muse S Athena: official documentation and open-source survey (2026-11-26)

What Muse publishes and what the open-source decoders have measured, checked against our own
hardware sitting of 2026-11-26 (firmware 3.1.31, BrainFlow 5.24.0, preset p1041). Only public
sources are cited. Muse's SDK documentation is confidential under its licence and is not quoted
here.

## What changed in MuFuse because of it

| Finding | Change |
|---|---|
| BrainFlow divides the raw battery value by 512; muse-rs, OpenMuse and muse.js use 256, and muse-rs checked 256 against the headset's own reading. **On our headband the status reply said 99.5% while BrainFlow's row said 49.7%.** | The battery is read from the headset's status reply (`bp`) and the row is doubled when it reads half of it (athena_status.py, brainflow_athena.py). |
| The status reply also carries the active preset (`ps`, e.g. 4161 = 0x1041); an unsupported preset is silently ignored by the headset. | A warning when the headset runs a different preset than the one asked for. |
| EEG full scale is ±725 µV (official product page), so a 1000 µV rail can never be reached. | Railed = within 2% of full scale (signal_check.py). |
| In bright light the ambient rows hit the 20-bit ceiling and every LED row reads 0. | Those frames are "too much light": shown, never used as data (optics.py). |
| Presets p20, p21, p50, p51, p60 and p61 produce no optics on the Athena. | Marked in athena.py. |
| Muse's brand guidelines forbid replicating their "horseshoe" contact indicator and ask third-party apps to say "Not an Official Muse application". | The live view uses a plain position map; the notice is in README and docs/BRAND.md. |

## Contact quality

- Muse grades each EEG sensor good / medium / poor about ten times a second from roughly the last
  second of raw EEG; blinks and muscle make it fail. The thresholds are not published.
- The Muse app checks the sensors, then calibrates for a minute; its starter guide says to wait
  30-60 s after adjusting the band.
- muse.js measured worn against off-head: samples within 2% of full scale 0.1-0.6% worn against
  25-40% on a desk; spread 10-63 µV worn against about 600 µV on a desk
  ([muse.js](https://github.com/Polobase/muse.js)).
- Our own sitting: a sensor not touching the skin read 100-550 µV with 85-100% of its power at
  60 Hz; a touching but moving sensor read high with under 25% at 60 Hz; good contact read 8-40 µV.
  That is the rule contact.py uses.
- The DRL/REF stream would show "on the head" directly, but BrainFlow does not pass it on.

## Hardware (official)

- Sensors TP9, AF7, AF8, TP10; reference at FPz with driven-right-leg electrodes beside it; dry
  silver-thread fabric. Fit: hair out of the way, wipe the sensors and the skin with a damp
  tissue or cloth, tighten while holding the forehead sensors. Glasses go on over the band; metal
  frames may interfere. ([product page](https://choosemuse.com/products/muse-s-athena),
  [starter guide](https://choosemuse.com/blogs/news/muse-s-athena-starter-guide))
- Optics: 5 optodes, 64 Hz, 20-bit, 850 / 730 / 660 nm. One central source and two photodiodes
  per side ([FCC 2ABZI-MS03](https://fccid.io/2ABZI-MS03)).
- EEG 14-bit at 256 Hz, ±725 µV. Battery 150 mAh, up to 10 h.
- Firmware 3.1.30 and 3.1.31: no public notes. Our F1 check confirmed the optics row order on 3.1.31.

## BrainFlow 5.24.0 (still the newest release)

- Release takes about 7 s while connected: two passes of stop, a 2 s sleep and unsubscribe before
  the disconnect; it is quick when the link is already down.
- No disconnect callback and no reconnect of its own; a dropped link reads as empty data.
- Without a name or address the scan takes any device whose name starts with "MuseS": pass the
  device name when it is known.
- `package_num` = 16-bit packet counter (gapless across sensors) shifted left 8, plus the
  per-sensor subpacket counter in the low byte.
- Source: [brainflow-dev/brainflow](https://github.com/brainflow-dev/brainflow),
  `src/board_controller/muse/muse_athena.cpp`.

## Licensing

- Muse's SDK is free for non-commercial use by application, and its licence forbids getting Muse
  data other than through the SDK. MuFuse reads the open Bluetooth stream through BrainFlow and
  should not sign that licence while it does.
  ([developers](https://choosemuse.com/pages/developers))

## Still open

- Source-detector distances (photos give an estimate only).
- Whether headset-side ambient subtraction is real (inferred, not stated).
- Thresholds for contact grades: starting values, to be tuned from saved sessions (feature 002).
