# Feature Specification: Signal Quality

**Feature Branch**: `002-signal-quality`

**Created**: 2026-11-26

**Status**: Draft

**Input**: User description: "For every stretch of a live or recorded session, MuFuse says which signal can be trusted,
and why not when it cannot: contact for each of the four EEG sensors, blinks, jaw and muscle tension, and head movement.
Later features read this one answer instead of judging quality themselves. It must keep working when only the two
forehead sensors (AF7, AF8) are usable, because the ear sensors are a known issue (`docs/KNOWN-ISSUES.md`, issue #12).
Roadmap gate: blinks, jaw clenches and head turns in a labelled test set are detected at 90% or better."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See which sensors can be trusted right now (Priority: P1)

The user wears the headband and opens the live view. For each of the four EEG sensors they see one of three contact
states: good, noisy, or no contact. When a sensor is not good, the view gives the reason in plain words: flat, at the
limit of its range, mostly mains hum (the sensor is not touching skin), or too loud (movement or a loose fit). The view
also says how many sensors are usable in total. When both forehead sensors are good and one or both ear sensors are not,
the view says the session is usable with reduced coverage and names the sensors that are out.

**Why this priority**: Every later feature depends on knowing which signal is real. It is also what the user needs
today: the ear sensors do not hold contact, and the user must be able to work with the forehead sensors alone.

**Independent Test**: On the simulator, lift one sensor, then make one sensor noisy, then drop both ear sensors. The
view shows the right state and reason for each sensor each time, and reports "usable with reduced coverage" in the last
case.

**Acceptance Scenarios**:

1. **Given** all four sensors have good contact, **When** the user watches the live view, **Then** all four show good
   and the view reports full coverage.
2. **Given** a sensor is lifted off the skin, **When** 2 seconds have passed, **Then** that sensor shows no contact
   with the reason "mostly mains hum", and the other sensors keep their own states.
3. **Given** a sensor is touching but the user is moving, **When** the signal is too loud, **Then** that sensor shows
   noisy with the reason "too loud", and not "no contact".
4. **Given** both ear sensors have no contact and both forehead sensors are good, **When** the user watches the live
   view, **Then** the view reports "usable with reduced coverage" and names TP9 and TP10 as out.
5. **Given** a sensor has just returned to good contact, **When** it has stayed good for 3 seconds, **Then** it is
   shown as good; until then it is shown as settling, with the time left.

---

### User Story 2 - Blinks, jaw tension and head movement are marked (Priority: P2)

While the signal is streaming, MuFuse marks three things that disturb brain signal, each with its time:

- every blink or large eye movement,
- stretches of jaw or muscle tension,
- stretches where the head is moving too much for the brain and optics signals to be trusted.

The live view shows them as they happen: a blink count, and whether tension or movement is present now. All three work
from the forehead sensors and the motion sensors. None needs an ear sensor.

**Why this priority**: Blinks and muscle activity are many times larger than brain signal. Without marking them, later
features would measure the face and call it the brain. Blink times are also a signal in their own right for later
features.

**Independent Test**: On the simulator, produce 20 blinks, 20 jaw clenches and 20 head turns at known times. At least
18 of each are marked within the allowed time of the true event, and quiet stretches stay unmarked.

**Acceptance Scenarios**:

1. **Given** the user blinks once, **When** the blink has ended, **Then** one blink is marked with its time, and the
   blink count rises by one.
2. **Given** the user clenches the jaw for 2 seconds, **When** the clench is under way, **Then** the live view shows
   muscle tension present, and the stretch is marked with its start and end.
3. **Given** the user turns the head, **When** the movement exceeds the limit, **Then** the stretch is marked as
   movement for the brain signal and for the optics signal.
4. **Given** neither forehead sensor has contact, **When** the user blinks, **Then** blink detection is reported as
   not available, and the blink count is shown as unknown, never as zero.
5. **Given** both ear sensors have no contact, **When** the user blinks, clenches or turns the head, **Then** each is
   marked exactly as it would be with the ear sensors in contact.

---

### User Story 3 - Review the quality of a recorded session (Priority: P3)

After a session, the user asks for its quality summary. It shows, for the whole recording:

- for each sensor, the share of time it was good, noisy and without contact,
- the number of blinks and the blinks per minute,
- the share of time marked for muscle tension and for head movement,
- for each sensor, the share of time that was clean: good contact with no blink, tension or movement mark.

The summary works on any recording, including those made before this feature existed.

**Why this priority**: It tells the user whether a session is worth keeping and whether the fit needs work, and it is
how the ear-sensor problem can be followed over time.

**Independent Test**: Record a simulated session with known faults at known times and request the summary. Every share
and count matches the known values within the stated tolerance.

**Acceptance Scenarios**:

1. **Given** a finished recording, **When** the user requests its quality summary, **Then** the shares and counts
   above are shown for each sensor and for the session.
2. **Given** a recording made with feature 001 before this feature existed, **When** the user requests its summary,
   **Then** it is produced without changing the recording.
3. **Given** a recording with a gap (the headband dropped out), **When** the summary is produced, **Then** the gap is
   reported as "no data" and is not counted as "no contact".

---

### User Story 4 - One quality answer for every later feature (Priority: P4)

Later features (measurements against baseline, check-ins, observations) do not judge quality themselves. For any sensor
and any stretch of time they ask one question, "is this clean?", and get yes or no with the reasons. The answer is the
same whether the data arrives live or is replayed from a recording.

**Why this priority**: If each feature judged quality in its own way, the same second of signal would be trusted by one
and rejected by another, and results could not be reproduced.

**Independent Test**: Run a simulated session live and record it. Replay the recording. The quality answers for every
sensor and every stretch are identical.

**Acceptance Scenarios**:

1. **Given** a stretch with good contact and no marks, **When** a later feature asks about it, **Then** the answer is
   "clean".
2. **Given** a stretch with a blink on a forehead sensor, **When** a later feature asks about it, **Then** the answer
   is "not clean" with the reason "blink", and the contact state is still reported as good.
3. **Given** the same data live and replayed, **When** quality is computed for both, **Then** every answer matches.
4. **Given** any quality answer, **When** it is inspected, **Then** it names the version of the quality rules that
   produced it.

---

### User Story 5 - Prove the detectors on labelled data (Priority: P5)

The user sits one short guided session with the headband on: cued blinks, cued jaw clenches, cued head turns, and
quiet stretches in between. MuFuse then scores its own detectors against the cues and prints a report: how many of each
were found, and how many false marks appeared in the quiet stretches. A second score is produced on a public set of
recordings from a similar headband, which is downloaded on request and never stored in the project.

**Why this priority**: It is the roadmap's exit gate for this feature. It comes last because the detectors must exist
first.

**Independent Test**: Run the guided session on the simulator. The score report shows the known number of cued events
and the number found, and states pass or fail against 90%.

**Acceptance Scenarios**:

1. **Given** a guided labelled session has been recorded, **When** scoring is run, **Then** the report gives found and
   total for blinks, clenches and head turns, the false marks in quiet stretches, and pass or fail for each.
2. **Given** the public set has been downloaded, **When** scoring is run on it, **Then** the report gives found and
   total for blinks and clenches on that set.
3. **Given** the public set has not been downloaded, **When** scoring is run, **Then** the report says so and scores
   the user's own session only.
4. **Given** a detector scores below 90%, **When** the report is printed, **Then** it says fail for that detector. The
   limit is not lowered to make it pass.

---

### Edge Cases

- **Headband not on the head:** when no sensor has contact, the view says the headband does not appear to be worn,
  instead of listing four separate faults.
- **Start of a session:** for the first seconds there is too little data to judge. Sensors are shown as settling, and
  no stretch is reported as clean or as faulty until there is enough data.
- **Gap in the data:** time inside a recorded gap is "no data". It is never "no contact", and it is left out of every
  share in the summary.
- **Motion data missing:** if the motion sensors deliver nothing for a stretch, the movement mark is "unknown" for
  that stretch, and the stretch is not reported as clean.
- **Only one forehead sensor in contact:** blinks and tension are still detected on that sensor, and the view reports
  the coverage as "one forehead sensor" and names the sensor that is out.
- **Long tension (talking, chewing):** a stretch of tension may last minutes. It is one stretch with a start and an
  end, not hundreds of separate marks.
- **Eyes closed:** no blinks are expected. Slow eye movements under closed lids must not be counted as a stream of
  blinks.
- **Blink during tension or movement:** a stretch may carry several reasons at once. All are reported.
- **A sensor that flickers between states:** the shown state must not flip more than about once a second, so the view
  stays readable. The stored answers keep the true times.
- **Mains frequency:** hum sits at 60 Hz in North America and at 50 Hz in most other regions. The hum check must
  recognise both without a setting.

## Requirements *(mandatory)*

### Functional Requirements

**Contact**

- **FR-001**: System MUST report a contact state for each of the four EEG sensors (TP9, AF7, AF8, TP10), separately,
  at least once a second: good, noisy, or no contact.
- **FR-002**: Every state other than good MUST carry a reason from a fixed list: flat, at the limit of its range,
  mostly mains hum, not connected (a floating input), too loud.
- **FR-003**: A sensor MUST be shown as good only after 3 seconds of unbroken good contact. A loss of contact MUST be
  shown within 2 seconds.
- **FR-004**: System MUST tell "no contact" apart from "touching but noisy", so that the user knows whether to reseat
  a sensor or to hold still.
- **FR-005**: System MUST report session coverage as one of four levels: full (four sensors good), reduced (both
  forehead sensors good, one or both ear sensors not), one forehead sensor (exactly one of AF7 and AF8 good), or
  none (neither forehead sensor good). Reduced coverage MUST be presented as usable. Every level below full MUST name
  the sensors that are out.
- **FR-006**: No result of this feature for AF7 or AF8, and no blink, tension or movement mark, may depend on the
  signal of TP9 or TP10.

**Blinks, tension, movement**

- **FR-007**: System MUST mark each blink or large eye movement with its time, using the forehead sensors.
- **FR-008**: System MUST report a muscle tension level from the forehead sensors and MUST mark stretches where it
  exceeds its limit, each with a start and an end.
- **FR-009**: System MUST mark stretches where head movement, measured by the headband's motion sensors, exceeds its
  limit, each with a start and an end. The mark applies to the brain signal and to the optics signal.
- **FR-010**: When a detector cannot work (no forehead sensor in contact, or no motion data), System MUST report
  "not available" or "unknown" for that stretch. It MUST NOT report zero events or a clean stretch.

**One answer**

- **FR-011**: For every sensor and every stretch of time, System MUST provide one combined answer: clean or not clean,
  with all reasons that apply (contact state, blink, tension, movement, no data, unknown).
- **FR-012**: The combined answer MUST be identical for a live stream and for the same data replayed from a recording.
- **FR-013**: Every quality answer and every summary MUST name the version of the quality rules that produced it.
- **FR-014**: Later features MUST be able to read the combined answer without repeating any quality judgement, and
  MUST be able to tell which reasons made a stretch not clean.
- **FR-015**: System MUST produce quality answers for any existing recording, including recordings made before this
  feature, without changing the recording.

**What the user sees**

- **FR-016**: The live view MUST show, for each sensor, its contact state and reason; the session coverage; the blink
  count; and whether tension or movement is present now.
- **FR-017**: System MUST provide a quality summary of a recorded session: for each sensor the share of time good,
  noisy, without contact and clean; the blink count and blinks per minute; the share of time marked for tension and
  for movement; and the time without data.
- **FR-018**: Colours in the live view and the summary MUST grade signal quality only. All wording MUST describe the
  sensor or the signal ("TP9 is not touching skin"), never the person's state ("you are tense").
- **FR-019**: A muscle tension mark MUST be presented as a disturbance of the signal. It MUST NOT be presented as
  stress, anxiety or any other state of the person.

**Proof**

- **FR-020**: System MUST provide a guided labelled session that cues blinks, jaw clenches, head turns and quiet
  stretches, and stores the cue times with the recording.
- **FR-021**: System MUST score the detectors against a labelled session and report, for each kind of event, the
  number found, the total, the false marks in quiet stretches, and pass or fail.
- **FR-022**: System MUST be able to score the blink and clench detectors on a public set of recordings that is
  downloaded on request. The set MUST NOT be stored in the project's repository.
- **FR-023**: The simulator MUST be able to produce each fault and event at known times: a lifted sensor, a noisy
  sensor, a flat sensor, a sensor at its limit, a blink, a jaw clench and a head turn. All behaviour of this feature
  MUST be covered by automated tests that run without a headband.
- **FR-024**: No data may leave the machine through this feature, except the download of the public set when the user
  asks for it. That download sends none of the user's data.
- **FR-025**: Any change to the quality rules MUST be checked against stored reference recordings with stated numeric
  tolerances, and MUST raise the version of the quality rules when an answer changes.

### Key Entities

- **Contact state**: for one sensor at one moment: good, noisy, no contact or settling, with a reason when not good.
- **Event mark**: a blink with its time; or a stretch of muscle tension or head movement with its start and end.
- **Quality answer**: for one sensor and one stretch of time: clean or not clean, the reasons, and the version of the
  quality rules.
- **Coverage**: for the session at one moment: full, reduced, one forehead sensor or none, with the sensors that are
  out.
- **Quality summary**: for one recording: the shares and counts of FR-017, and the version of the quality rules.
- **Labelled session**: a recording with cue times for blinks, clenches, head turns and quiet stretches.
- **Score report**: for one labelled session or the public set: found, total, false marks and pass or fail for each
  detector.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a guided labelled session on the headband with at least 20 cued events of each kind, at least 90% of
  blinks, 90% of jaw clenches and 90% of head turns are marked.
- **SC-002**: In the quiet stretches of the same session, muscle tension and head movement are each marked in at most
  5% of the time, and with eyes closed at most 2 blinks a minute are marked.
- **SC-003**: On the public set, at least 90% of cued blinks and 90% of cued jaw clenches are marked.
- **SC-004**: A lifted sensor is shown as "no contact" within 2 seconds in at least 9 of 10 lifts, and is never shown
  as "noisy" for more than 2 seconds while lifted.
- **SC-005**: Replaying a recording gives quality answers identical to those computed live, for 100% of sensors and
  stretches.
- **SC-006**: When the signal of both ear sensors is replaced by a no-contact signal, every result for AF7 and AF8 and
  every blink, tension and movement mark is unchanged.
- **SC-007**: The quality summary of a 60-minute recording is ready in under 30 seconds.
- **SC-008**: With quality judging switched on, a 10-minute recording still has under 0.5% missing samples on every
  stream, and the live view still updates at least once a second.
- **SC-009**: 100% of the texts this feature can show describe a sensor or a signal. None describes the person.
- **SC-010**: The automated tests run without a headband in under 2 minutes, and coverage stays at 80% or above.

## Assumptions

- **Who and where**: one user, one headband (Muse S Athena), one computer. Nothing here is a medical judgement.
- **Ear sensors**: TP9 and TP10 are judged like the other sensors, but nothing depends on them until issue #12 is
  closed. The acceptance checks P0 and H8 of feature 001 are not changed by this feature.
- **Builds on feature 001**: the live view already grades each sensor's contact from its last second of signal, with
  a reason and a 3-second hold before "good". That grade is a fitting aid: it exists only on screen and only live.
  This feature keeps its behaviour where it is already correct and turns it into the one answer of FR-011, which also
  holds for recordings.
- **Reference recordings**: the reference recordings of FR-025 that live in the project are made by the simulator.
  The user's own labelled session is the reference from the real headband, and it stays on the user's machine.
- **Stretch length**: quality is judged in stretches of about one second. The exact length is a planning decision.
- **Jaw tension without ear sensors**: jaw muscles sit closer to the ear sensors than to the forehead. It is assumed
  that a clench is still strong enough on AF7 and AF8 to reach 90%. If the labelled session shows it is not, the result
  is reported as a fail and the spec is revisited; the limit is not lowered quietly.
- **Labels**: in the labelled session a cue is the label. An event counts as found when a mark starts within 2 seconds
  after its cue. Cues are at least 3 seconds apart, so a mark belongs to one cue only. The score report states the
  allowed time.
- **Public set**: recordings from a Muse 2, which has the same four sensor sites, with cued blinks and jaw clenches
  (`docs/research/2026-11-26-prior-art-and-datasets-survey.md`, section 3.2). Head turns are scored on the user's own
  session only, because the public set is not relied on for motion data.
- **The headband gate needs a sitting**: SC-001, SC-002 and SC-004 need the user to wear the headband for one guided
  session of about 10 minutes. All other criteria are checked on the simulator.
- **Personal recordings stay local**: the labelled session is a personal recording. It is never committed. Only the
  numbers of the score report are shared.
- **Storage**: quality answers are computed from the raw recording when they are needed. This feature adds no new
  stored file except the cue times of a labelled session, which are deleted with their recording.
- **Out of scope**: the quality of the pulse signal from the optics (feature 003), the fNIRS signal (feature 004),
  correcting or cleaning the signal (this feature marks, it does not repair), any statement about the person's state,
  and the desk strip (feature 005, which will show these same answers).
