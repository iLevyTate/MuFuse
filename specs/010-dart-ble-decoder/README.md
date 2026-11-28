# 010 Dart Athena BLE decoder — design note (planned, not started)

**Goal.** The app (Phase 1) talks to the headband itself, without Python or BrainFlow: a Dart
package that connects over Bluetooth LE, starts a preset, and turns the Athena's notifications into
the same samples the Python rig records (EEG, motion, optics, battery), stamped the same way
(`acquisition/timing.py`: retime, never drop, keep gaps).

**Gate (ROADMAP).** "Matches the Python golden decode": a stored capture of raw notifications,
decoded by the Dart package, equals the Python reference decode of the same bytes sample for sample
(EEG and optics to the last count, timestamps within one sample period), on every firmware in the
fixture set.

## Why a golden capture first

BrainFlow cannot be the reference for the same bytes: only one program can be connected to the
headband, and BrainFlow decodes inside its C++ core with no way to feed it stored notifications.
So the reference is a small Python decoder of raw notifications, checked against BrainFlow on
**statistics of separate sittings** (sample rates, value ranges, packet-counter continuity, the 001
acceptance checks), and the Dart package is checked against that decoder on the **same bytes**.

## Steps (each its own PR)

1. `mufuse capture-raw` (Python, `bleak`, MIT): connect, send the preset, write every notification
   as received (characteristic, arrival time, bytes) to an append-only file beside a manifest with
   the firmware version. Owner sittings: 2 minutes per preset (p1034, p1035, p1041, p1042), on
   each firmware the owner has. Personal recordings stay out of git; a short fixture is committed
   only from a sitting the owner chooses to share.
2. `acquisition/athena_wire.py`: the Python reference decoder of those files (packet counter,
   subpacket tags, 0x88 battery, 14-bit EEG at 1450/16383 µV per count as BrainFlow 5.23, optics in
   wire order). Checked against BrainFlow on separate sittings as above; it can also replay a raw
   capture as a `HeadbandSource`, so every Python feature runs on it.
3. `app/packages/athena/` (pure Dart): the same decoder, tested on the fixture against the Python
   decode exported as golden JSON. Then the link layer on `universal_ble` (BSD-3), with a one-day
   spike first: does it deliver the notification rate on Windows and Android without loss (count
   the 16-bit packet counter)?

## Decisions (defaults taken; change them here first)

1. **Pure Dart**, no Rust or C core: neurofeed's Flutter + Rust mix slowed it down, and the decode
   is byte unpacking, which Dart does well. Elata's Rust decoder (MIT) is a second reference to
   compare against, not a dependency.
2. **`universal_ble`**, not `flutter_blue_plus` (its licence is not open for commercial use).
3. **The Python rig stays the reference.** Any disagreement is settled in Python first, with a test.
4. **Firmware is part of the fixture.** 3.1.19 sent notifications of up to 244 bytes, 3.1.29 up to
   116: a fixture from one firmware does not cover the other. The owner's unit is 3.1.31.

## Open questions (the owner's)

- Will MuFuse ever be distributed for profit? Several licence answers (BLE package, models) depend
  on it.
- Which firmware versions can be captured? One unit covers one firmware at a time.
- Is a short raw capture from the owner's head acceptable to commit as a public test fixture (it
  holds about two minutes of EEG), or should the fixture be the simulator's bytes plus a private
  local check?

## Constitution Check

I: local only; raw captures are personal data and stay out of git unless the owner shares one.
IV: the decoder is deterministic code checked against a reference on the same bytes.
VIII: the Dart package produces the same samples as the Python rig, so features ported in 011 can
be checked against the golden frames already in `tests/data/features_reference/`.

## Done

- [ ] `mufuse capture-raw` and the owner's raw sittings (needs the headband)
- [ ] Python reference decoder, checked against BrainFlow
- [ ] `universal_ble` spike
- [ ] Dart decoder matching the golden decode
