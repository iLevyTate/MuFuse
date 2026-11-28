# 009 Paced breathing and first exercises — design note

**Goal.** A guided paced-breathing session (about six breaths a minute) with the pulse measured
before, during and after; and two short on-screen exercises (stepping back from a thought,
watching an urge). Everything is described against the wearer's own before-phase; nothing is
said about health.

**Gate (ROADMAP).** "Breathing session raises RMSSD vs pre-session in the user's own data."
Each session reports raised / not raised for both the beat-interval swing (primary) and RMSSD
(experimental). In CI the simulator's scripted wearer, whose pulse carries a known breathing
swing, must show a clearly bigger swing while pacing. The verdict over several real sessions is
the owner's (not a show stopper).

## What it delivers

- `src/mufuse/exercises/breathe.py`: the guide, the rehearsal wearer, the measures, the report.
- `src/mufuse/exercises/library.py` and `scripts/*.toml`: the two exercise scripts as guides.
- `mufuse breathe [--source athena|sim] [--rate 6] [--minutes 5] [--out DIR] [--check/--no-check]`.
- `mufuse exercise defusion|urge [--source athena|sim]`: on screen only, or recorded with one.
- Simulator: respiratory sinus arrhythmia on the scripted wearer (`Wearer.rsa`).

## Decisions (defaults taken; change them here first)

1. **Session.** 2 min sitting quietly, N minutes paced (default 5 at 6 a minute, allowed 3–12 a
   minute and 1–30 minutes), 2 min quietly again; markers `b:before`, `b:pace`, `b:after`,
   `b:end`. Pacing cues every half breath ("Breathe in (3 of 30)" / "Breathe out"), kept out of
   the step list (`Cue.step = False`) so the guide panel stays short. The 002 pre-flight fit
   check runs first, exactly as in `quality label`.
2. **Primary measure: the beat-interval swing.** Per breath-length window (60 / rate seconds,
   the same windows in every phase), max minus min of the plausible beat intervals (at least 3);
   the median over windows. At 64 Hz it is measured far better than RMSSD (survey 3.4; OpenHRV
   feeds back the same swing). RMSSD is reported, labelled experimental: on the simulator it
   reads 25–75 ms on a pulse with no variability at all (003 note).
3. **Beats** come from the 003 pulse code (`combined` over the LED rows, `beat_times`,
   `plausible`), over each whole phase.
4. **Result line**, description only: "During paced breathing the beat-interval swing was X ms
   against Y ms before (RMSSD a → b, experimental)", then raised / not raised for each measure.
5. **Simulator.** `Wearer.rsa = ((from, to, breaths a minute, swing ms), ...)`: the heart rate
   swings at the breathing rate so beat intervals swing by `swing ms` peak to trough; the phase
   is a closed-form integral, so it is the same however samples are read. Empty by default: every
   earlier rehearsal, reference and golden file is unchanged (their tests pass untouched). The
   breathe rehearsal wearer: 15 a minute with a 30 ms swing at rest, the paced rate with a 150 ms
   swing while pacing, following the cues 0.4 s late.
6. **Exercises.** Two scripts written for MuFuse (not copied from published scripts), each four
   minutes of short steps, plain words, no health claims, nothing said about the person. Every
   line goes through the 007 output filter (`mufuse.chat.filter.check`) in a test.
7. No new dependency.

## Constitution Check

II: describe only, before against during, no states. I: local only. IV: the measures are code
with tests; the rehearsal wearer is a known input. VI: no model involved.

## Open questions

- Is a real forehead pulse clear enough (pulse share >= 0.5) to see the swing at 6 a minute?
- Should the pacing tone also sound (eyes may be closed)? Not now: screen cues only.

## Hardware check (owner, not a show stopper)

`uv run mufuse breathe --source athena` on a few days; the multi-session verdict is the share
of sessions with the swing raised.

## Done

- [x] guide, markers, pacing cues out of the timeline
- [x] RSA in the simulator, earlier outputs unchanged
- [x] swing, heart rate, RMSSD per phase; report
- [x] `mufuse breathe`, `mufuse exercise defusion|urge`
- [x] docs
- [ ] sessions on the headband (owner)
