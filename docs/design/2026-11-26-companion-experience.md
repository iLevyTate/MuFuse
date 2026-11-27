# MuFuse companion experience: design (2026-11-26)

**Status:** approved by the owner on 2026-11-26, including the four decisions at the end.
Nothing in this document is built yet.
**Rules:** `.specify/memory/constitution.md`. **Evidence:** `reports/Muse EEG self awareness research.md`.

## Goal

While you work at a desk wearing the headband, MuFuse notices when your signals shift away from
your own baseline and asks what was going on. Over a few weeks it learns what your daydreaming,
worry and focus look like, so that "what is my brain doing right now?" gets an honest answer.

The system notices; the person names. That split is the whole design.

## What it can and cannot tell you

| You want to know | What the headband shows | What MuFuse may say |
|---|---|---|
| Daydreaming, mind-wandering | Blink rate, eye movement, alpha rhythm, stillness | A description, then a personal pattern once it has earned one |
| Anxiety | Arousal only: heart rate up, heart-rate variability (HRV) down, muscle tension | "Heart rate is up against your baseline." It cannot tell worry from excitement or coffee |
| Rumination, stuck on a thought | Low HRV held while sitting still | A reason to ask you. Never a name for it |
| Low or depressed mood | Nothing moment to moment | Nothing from the signals. Your own check-ins are the only source |
| "What does my brain state look like?" | All of the above against your baseline | The brain-state card below |

## The journey

1. **Put it on.** The fit check says READY or which sensor to fix (already built in the live view).
2. **Settle.** Two quiet minutes set today's baseline. Baselines from earlier days are kept too.
3. **Set a focus item** (optional): "finish the report". The session is measured against it.
4. **Work.** The strip stays quiet. It shows signal quality and one line of "now against baseline".
5. **Check-in.** A soft tone and one question, on a shift or at a random moment. One tap answers it.
6. **Ask.** Open the chat at any time: "what are you seeing?"
7. **Wrap up.** A short recap in the chat, and a review page with the session's timeline.
8. **Over weeks.** Patterns appear with their counts: "this matched daydreaming 6 of 9 times".

Desk sessions of 30 to 90 minutes come first. All-day wear comes second and uses the same parts.

## Surfaces

### The strip

A small window that stays on top of other windows.

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│ ● good signal  42:10  blinks higher · heart rate steady  [check in] [chat] [snooze] │
└────────────────────────────────────────────────────────────────────────────────────┘
   quality only  session  now against your baseline
```

- The dot grades signal quality only, never the person (`docs/BRAND.md`).
- When the signal is poor, the strip names the sensor to fix and shows no reading.
- A badge appears whenever anything is being sent to a cloud model.

### The check-in

- One neutral question: "What's on your mind?" It never suggests an answer.
- One-tap answers, shown in a different order each time: on task, planning, daydreaming, worry,
  stuck on a thought, memory, urge, feeling low, nothing much, or your own words.
  The list is yours to edit.
- At most one check-in every 15 minutes. Snooze for an hour with one click.
- At least 30% of check-ins come at random moments. Without them MuFuse cannot learn whether its
  detectors do better than chance.
- No check-ins while the signal is poor, while you are moving a lot, or during a focus block you
  have marked as do-not-disturb.
- Each answer is stored with its source (random, triggered by a shift, started by you). The three
  are never mixed when hit rates are counted.

### The chat

The strip opens into a chat window. It talks first at four moments: the start of a session, after
a check-in, on a notable shift (unless snoozed), and at the end of a session.

Every answer about signals has three parts:

1. **What changed:** "Blink rate about double your baseline for four minutes. Heart rate steady."
2. **How far to trust it:** "Good signal on three of four sensors. Jaw tension may be raising TP9."
3. **A question back:** "What was going on for you just then?"

Other rules:

- Text first. Voice (speech in and out) is added later with feature 007.
- A local model (Ollama) is the default. A cloud model (Claude API) is opt-in, receives summaries
  only and never raw signal, and shows a badge while active.
- Every number is computed by code. The model only words the answer.
- A fixed filter blocks mind-reading and diagnostic wording before anything is shown.
- Crisis wording triggers a pre-written response with crisis resources. The model cannot change it.
- No character and no relationship framing. After a heavy answer it stops probing and offers
  "park this for later". Long late-night sessions are rate-limited.
- If no model is available, the three-part answer is produced from templates.

### The brain-state card

At the top of the chat, and on request from the strip:

```
Now, against your baseline                        signal: good (4 of 4)
  Blink rate        higher      ▲▲      grounded
  Alpha rhythm      lower       ▼       grounded
  Heart rate        usual       ·       grounded
  HRV               lower       ▼       grounded
  Muscle tension    usual       ·       grounded
  Stillness         very still  ▲▲      grounded
  Closest personal pattern: daydreaming, 6 of 9 times   (hypothesis)
```

There is never a single score, and nothing to maximise.

### The review page

After a session: a timeline of shifts, check-ins, markers and gaps. Each week: patterns, each with
its count, its effect and the word "hypothesis". This is feature 008.

## How it speaks

| Level | Example | When it is allowed |
|---|---|---|
| Description | "Blink rate about double your baseline." | Always, when signal quality is good |
| Personal pattern | "This looks like what you have called daydreaming, 6 of 9 times." | After the pattern beats chance on your own check-ins, or earlier if you opt in (see below) |
| Label | "You are anxious." | Never. Blocked by the filter |

### Refining what it tells you

- One tap on any message: useful, not useful, or wrong.
- Plain requests in the chat: "stop telling me about blinks", "tell me sooner when I drift".
- A settings page lists what it has learned, each pattern's hit rate, and every preference.
  Each one can be undone.

## Early feedback

The request is that MuFuse starts talking early and gets refined later, even before it is accurate.
The constitution (principle V) keeps a new pattern silent until it beats chance on your own data.

Most of the request needs no rule change: descriptions, check-ins and "what are you seeing?" are
allowed from day one. Only personal-pattern statements are held back.

**Amendment to principle V (constitution 1.1.0):** patterns stay silent by default. You may switch on early
feedback, and then unproven patterns are shown with the tag "speculative · unproven for you".
Hit rates are still tracked. A pattern loses the tag only after it beats chance. Principle II
(describe, don't label) still applies in full.

## Architecture

```
headband ── BrainFlow ──► Python engine ──► mufuse serve ──► Flutter desktop app
                          (one process)     (this PC only)    (strip, chat, review)
                               │
                               └──► model adapter: Ollama (default) │ Claude API (opt-in)
```

| Part | Does | Talks to |
|---|---|---|
| Acquisition, recording | Reads the headband, saves sessions (feature 001, built) | BrainFlow |
| Quality | Contact, blinks, jaw, motion gate (002) | Acquisition |
| Features and baseline | Blink rate, alpha, heart rate, HRV, tension, stillness, each against your baseline (003) | Quality |
| Check-in scheduler and store | Decides when to ask; stores answers by source (005) | Features, clock |
| Observations and patterns | Neutral "this shifted" events; plug-in patterns with hit rates (006) | Features, store |
| `mufuse serve` | Sends events to the app and takes commands from it | All of the above |
| Model adapter | Turns a structured summary into words; runs the filter and the crisis check (007) | Ollama or Claude API |
| Flutter app | Strip, check-in, chat, brain-state card, review page | `mufuse serve` only |

- **Events from the engine:** quality, features (once a second), observation, check-in, session.
- **Commands from the app:** mark, answer, snooze, ask, set focus, feedback.
- `mufuse serve` listens on this PC only (127.0.0.1) and needs a token that changes every run.
  Its message format is versioned and joins the portable core contract (principle VIII), so a phone
  engine can later serve the same app.
- The fast loop (shift detected, tone played) runs in the engine with no model involved. The
  model is only ever in the slow loop (principle VI).

**Why this stack:** the Python engine works and is verified on the headband. Flutter is already
the constitution's choice for the app, and the same screens can run on a phone later. The Dart
decoder and feature port (roadmap 010 and 011) wait until a phone engine is actually needed.

## When things go wrong

| Situation | What the person sees |
|---|---|
| Headband drops out | "Reconnecting". No readings. The gap is recorded |
| Poor contact | The sensor to fix. No readings and no check-ins triggered by shifts |
| No model available | Template answers. Check-ins and the card still work |
| Cloud model fails | Falls back to the local model; the badge goes out |
| Engine not running | The app offers to start it |
| Crisis wording in the chat | The fixed response, whatever the model is doing |

## Testing

- The simulator and recorded sessions drive `mufuse serve` in CI; its messages are checked against
  stored examples.
- The scheduler is tested with an injected clock, including the 30% random share and the
  15-minute limit.
- The wording filter and the crisis response have their own test suites.
- The Flutter app is tested against a replayed event stream, with stored screenshots.
- Each feature keeps a short manual check with the headband on.

## Build order

Each step is one Spec Kit feature on its own branch.

| Step | Feature | What you can do after it |
|---|---|---|
| 1 | 001 acquisition: finish hardware checks, merge | Record sessions |
| 2 | 002 signal quality | Trust or discard each stretch of signal |
| 3 | 003 features and baseline | See the brain-state numbers in the terminal |
| 4 | 005 check-ins, with `mufuse serve` and the strip | Use the strip at your desk and answer check-ins |
| 5 | 006 observations and patterns | Shifts trigger check-ins; patterns start earning hit rates |
| 6 | 007 chat | Ask "what are you seeing?"; it talks first |
| 7 | 009 breathing | A guided breathing exercise with live HRV |
| 8 | 008 review page | Timeline and weekly patterns |

## Decisions (2026-11-26)

1. **Early feedback:** approved. Principle V is amended in constitution 1.1.0.
2. **Roadmap order:** fNIRS (004) moves after step 5, since no goal above depends on it, and the
   Flutter strip comes forward into step 4. `docs/ROADMAP.md` is updated.
3. **Default check-in answers:** the list above. It stays editable.
4. **Craving cue exercise:** a later note in the roadmap, not a feature yet.

## Not in this design

The phone app, the ring, bone-conduction audio, neurofeedback scores, and anything diagnostic.
