# Feature Specification: Headband Acquisition & Recording

**Feature Branch**: `001-headband-acquisition`

**Created**: 2026-11-25

**Status**: Draft

**Input**: User description: "Connect the Muse S Athena to my Alienware with as little friction as possible, stream every
signal it has (EEG, motion, optics/fNIRS, battery), show me whether the electrodes are making contact, and record
sessions with time-stamped event markers so later features can learn from them. It must work without the headband for
development and testing, and it must be built with quality from the start."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Connect and see live signal (Priority: P1)

The user puts on the headband, runs one command, and within seconds sees that the headband is connected, its battery
level, and a live per-sensor readout (EEG on all four sites, motion, optics) updating continuously. No manual
operating-system pairing is needed. If more than one headband is nearby, or the last-used one is known, the right one is
chosen without the user typing an address.

**Why this priority**: Nothing else in MuFuse can exist without a reliable live stream; this is also the "is my
hardware working?" check.

**Independent Test**: With the headband powered on and the official Muse app closed, run the connect command and
observe live values for every stream within 15 seconds; disconnect cleanly with Ctrl+C.

**Acceptance Scenarios**:

1. **Given** a powered-on headband and no saved device, **When** the user runs the connect command, **Then** the system
   discovers the headband, connects, and shows live EEG, motion, optics and battery within 15 seconds.
2. **Given** a previously used headband, **When** the user runs the connect command, **Then** it reconnects to that
   headband without asking.
3. **Given** no headband is reachable, **When** the user runs the connect command, **Then** the system reports within
   30 seconds that no headband was found, with the likely causes (powered off, connected to another device/app,
   Bluetooth off).

---

### User Story 2 - Record a labelled session (Priority: P1)

The user starts a recording, optionally naming the activity ("deep work", "breath-hold test"). While recording they press
a key to drop a time-stamped marker ("something just happened") or a numbered marker (block start/end for validation
protocols). When they stop, the session is saved to their own disk as a self-describing file set that can be reloaded
later with all streams aligned on a common clock.

**Why this priority**: Every later feature (signal quality, features, fNIRS validation, interpreters) trains and tests
on recorded sessions with markers. Without recordings there is no quality gate for anything downstream.

**Independent Test**: Record two minutes with three markers, reload the session, and confirm all streams, markers,
device metadata and preset are present and aligned.

**Acceptance Scenarios**:

1. **Given** a connected headband, **When** the user records for 10 minutes, **Then** the saved session contains every
   stream at its nominal rate with fewer than 0.5% missing samples and a summary of any gaps.
2. **Given** a recording in progress, **When** the user presses a marker key, **Then** a marker with the key's label and
   a timestamp is stored and is visible on reload at the correct position (±1 sample of the stream nearest in time).
3. **Given** a finished session, **When** it is reloaded, **Then** device ID, firmware preset, sampling rates, channel
   names, software version and start time are all present.

---

### User Story 3 - Develop and test without the headband (Priority: P1)

A developer (or CI) runs the exact same connect/stream/record flows using a simulated headband or by replaying a saved
session, so the full pipeline can be tested automatically on any machine.

**Why this priority**: Constitution Principle VII — quality gates must run in CI without hardware.

**Independent Test**: In CI, record from the simulated headband, reload the result, and assert stream shapes, rates
and marker positions.

**Acceptance Scenarios**:

1. **Given** no headband, **When** the user selects the simulated source, **Then** all streams behave like the real
   device's streams (same channel names and rates).
2. **Given** a saved session, **When** the user selects playback of that session, **Then** downstream consumers receive
   the recorded data in original timing (or as fast as possible when requested).

---

### User Story 4 - Survive real-world dropouts (Priority: P2)

Bluetooth drops happen (walking away, interference, headband shifts). The system detects a stalled stream, reconnects
automatically, keeps the recording going, and marks the gap rather than silently stitching data together.

**Why this priority**: Long naturalistic sessions are the point of the product; silent gaps would corrupt every later
analysis.

**Independent Test**: During a recording, turn the headband off for 10 seconds and back on; the session continues and
the gap is recorded with start/end times.

**Acceptance Scenarios**:

1. **Given** a recording in progress, **When** no data arrives for 3 seconds, **Then** the system reports "signal
   lost", attempts reconnection with backoff, and records a gap marker.
2. **Given** reconnection succeeds, **When** data resumes, **Then** the recording continues in the same session and the
   gap's duration is stored.

---

### User Story 5 - Choose the sensor preset (Priority: P3)

The user can choose which headband preset to use (e.g., more optics channels vs. lower power) and the session records
which one was active.

**Why this priority**: The fNIRS milestone needs to compare presets; defaults are fine until then.

**Independent Test**: Connect with two different presets and confirm the number of optics channels and the stored
preset differ accordingly.

**Acceptance Scenarios**:

1. **Given** a valid preset name, **When** connecting, **Then** that preset is used and stored in the session.
2. **Given** an invalid preset name, **When** connecting, **Then** the system refuses before connecting and lists the
   valid presets.

### Edge Cases

- The official Muse app (or a phone) is already connected — the headband is invisible; the error must say so.
- Battery reaches a low level during recording — warn at 15%, keep recording until the device stops.
- Disk fills up or is unwritable — stop safely, keep everything written so far readable, report the error.
- User presses Ctrl+C mid-recording — session is finalized and readable, not corrupted.
- Clock jumps (sleep/hibernate) — timestamps stay monotonic within a session; the jump is recorded as a gap.
- Streams arrive at different rates and slightly different start times — alignment must use device timestamps, not
  arrival order.
- Multiple headbands nearby — choose saved device; otherwise list candidates and choose the strongest signal, never
  silently connect to an unknown one when a saved device is configured.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST discover and connect to a Muse S Athena without OS-level pairing and remember the last-used
  device for automatic reconnection.
- **FR-002**: System MUST stream EEG (TP9, AF7, AF8, TP10 at 256 Hz, plus auxiliary EEG channels when the preset
  provides them), accelerometer and gyroscope (52 Hz), raw optics (4/8/16 channels at 64 Hz depending on preset) and
  battery.
- **FR-003**: System MUST expose a single source abstraction with three interchangeable implementations: real headband,
  simulated headband, and recorded-session playback. Downstream code MUST NOT depend on which is used.
- **FR-004**: System MUST record sessions to the user's local disk only, in an open, documented, self-describing
  format including per-stream data, timestamps, channel names, sampling rates, preset, device identity, software
  version, and session notes.
- **FR-005**: System MUST support time-stamped user markers during recording (free "moment" markers and labelled /
  numbered block markers), stored on the session's common clock.
- **FR-006**: System MUST detect stream stalls (no data for 3 s), attempt automatic reconnection with backoff, and record
  gaps explicitly; it MUST NOT interpolate across gaps.
- **FR-007**: System MUST report per-session data completeness (expected vs. received samples per stream).
- **FR-008**: System MUST finalize a readable session on normal stop, Ctrl+C, device loss, or write errors.
- **FR-009**: System MUST validate the requested preset before connecting and record the active preset.
- **FR-010**: System MUST provide a live terminal view showing connection state, battery, per-stream sample rates and a
  rough per-EEG-channel signal indicator (amplitude range / flat-line / railed). Full contact-quality scoring is
  deferred to feature 002.
- **FR-011**: System MUST provide a command-line interface for: listing devices, live streaming, recording, and
  inspecting a saved session.
- **FR-012**: All acquisition behavior except the real-device driver MUST be covered by automated tests that run
  without hardware; real-device tests MUST exist and be runnable manually.
- **FR-013**: No acquired data may be transmitted off the machine by this feature.

### Key Entities

- **Device**: a specific headband — name/serial, address, firmware preset, last-seen time.
- **Stream**: one signal family (EEG, motion, optics, battery) — channel names, nominal rate, units, samples with device
  timestamps.
- **Session**: one recording — ID, start/end time, notes/activity label, device, preset, software version, streams,
  markers, gaps, completeness summary.
- **Marker**: a timestamped label — kind (moment, block-start, block-end, system), label text, source (keyboard,
  ring later, system).
- **Gap**: an interval with no data on a stream — start, end, reason (stall, disconnect, reconnect).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From headband power-on to live signal on screen in ≤ 15 seconds in ≥ 9 of 10 attempts.
- **SC-002**: A 10-minute recording has < 0.5% missing samples on every stream when the headband is within 2 m.
- **SC-003**: After a 10-second headband power cycle, streaming resumes automatically within 20 seconds and the gap is
  recorded with duration accurate to ±0.5 s.
- **SC-004**: Markers on reload sit within ±1 sample (±4 ms for EEG) of their capture time.
- **SC-005**: 100% of sessions interrupted by Ctrl+C or device loss reload without error.
- **SC-006**: The automated test suite runs with no hardware in < 2 minutes and covers ≥ 80% of non-driver code.

## Assumptions

- Phase 0 runs on the user's Windows 11 desktop with built-in Bluetooth LE; macOS/Linux are not targeted yet but not
  intentionally broken.
- The proven open-source BrainFlow library (5.22+, currently 5.24) is the device driver; its Athena support is new, so
  the driver sits behind the source abstraction so it can be swapped (e.g., OpenMuse) without touching other code.
- Only one app can connect to the headband at a time; the user closes the official Muse app first.
- Default preset is the driver's default (p1041, 16 optics channels); low-latency mode on.
- Recording format: one folder per session containing columnar numeric files per stream plus a JSON manifest (chosen
  for openness and easy loading in Python now and Dart later). Exact format decided in the plan.
- Personal recordings live outside the repository (`recordings/`, git-ignored).
- Signal-quality scoring, filtering, features, and fNIRS conversion are out of scope (features 002–004).
