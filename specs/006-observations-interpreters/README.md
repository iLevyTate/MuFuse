# 006 Observations and interpreter plug-ins — design note

**Goal.** Notice when a signal moves away from the wearer's own baseline (an *observation*: neutral,
"blink rate higher than usual for 40 s"), let that offer a check-in, and let *interpreters* guess
what a moment was, silently, until the wearer's own random check-ins show the guess beats chance.

**Gate (ROADMAP).** The first interpreter ("attention drift") is evaluated in shadow mode against
random probes. In CI: the evaluation on synthetic labels (a planted effect is found, no effect is
not), the look schedule, promotion and demotion, the early-feedback tag. On real data the owner's
weeks of use decide; a verdict needs about 90–100 random-probe answers (survey 3.7), so "not yet
known" is the expected state for weeks and is said so.

## What it delivers

- `src/mufuse/observe/observations.py`: neutral observations from feature frames.
- `src/mufuse/observe/interpreters.py`: the `Interpreter` protocol, TOML manifests (stdlib
  `tomllib`), a first-party allow-list registry, and the first interpreter `attention_drift`.
- `src/mufuse/observe/evaluate.py`: hit rate against the random base rate, AUC, a permutation test
  shuffled within each day, the look schedule, promote / demote.
- Store: a `scores` table (every interpreter's score at every check-in, any source) and the
  interpreter states; `mufuse serve` publishes `observation` and, only with early feedback on,
  `insight` messages, and offers a `shift` check-in on each new observation.
- `mufuse interpreters` (status, labels, hit rate vs base rate, AUC, p, next look) and
  `mufuse interpreters feedback on|off [--id ID]`.

## Decisions (defaults taken; change them here first)

1. **Observation.** Per series with a baseline (003), the median z of the last 15 s (Ronca 2025:
   Muse indices need 10–15 s of smoothing). It starts when |median z| ≥ 2 and ends when it falls
   under 1 (hysteresis, so it does not flicker). One observation per series at a time. Words are
   made in code from 005's describe words: "<series> higher than usual since 12:04".
2. **Shift check-ins.** A new observation offers a `shift` check-in; 005's scheduler decides
   (spacing, quiet, ≥ 30% random).
3. **Interpreter.** A manifest (TOML) names: id, title, evidence tier, the answers it is about
   (its *target*), the series it needs and the share of the window they must be present, a
   window (≥ 15 s), a firing threshold, the approved phrasing, and the look schedule. Code gives
   a score from the frames of the window before a check-in; higher = more likely the target.
4. **attention_drift** (tier *Speculative*): target answers daydreaming, stuck on a thought,
   memory; score = mean over the last 30 s of (z blink rate + z alpha share) / 2. Both rise
   during mind wandering in some studies and not in others; that is why it starts in shadow.
5. **Shadow mode.** Every interpreter's score is stored at every check-in, whatever its state.
   Nothing it says is shown unless it is promoted, or early feedback is on.
6. **Evaluation uses random check-ins only** (constitution V). Hit rate = share of target answers
   among random check-ins where it fired; base rate = share among all random check-ins. AUC of
   score against target. p from 2000 label shuffles within each day (blocked).
7. **Looks.** Judged only when the random answers with a score reach 50, 100, 150, ... (fixed in
   the manifest), never in between: repeated looks would find an effect by chance.
8. **Promote** at a look when AUC > 0.5, p < 0.05 and hit rate > base rate. **Demote** at a later
   look when that no longer holds. Promotion removes the tag; demotion brings back shadow mode.
9. **Early feedback** is off by default, per interpreter or for all, off again in one action.
   With it on, an interpreter in shadow mode that fires is shown with the tag
   "speculative · unproven for you". It never changes scoring, looks or the random share.
10. **Phrasing.** The approved phrasing is a description with a question: "Blink rate and alpha
    are up on your baseline, which in your answers has gone with daydreaming n of m times. What
    was going on?" Counts come from code. No "you are".

Not in 006: trained (scikit-learn) interpreters; they need labels first and come once a person has
about 100 random answers. Clock-only and blink-and-motion-only baselines are noted for that step.

## Constitution Check

II: observations and insights describe signals and invite the wearer's account. IV: manifests
carry a version; scores are stored with the features and rules versions. V: shadow first, random
probes only, fixed looks, the opt-in tag. VI: no model, no network.

## Open questions

- Is a 2 SD start too strict for blink rate, which moves a lot?
- Should a demoted interpreter need two failing looks in a row (less flapping)?

## Done

- [x] observations
- [x] interpreter protocol, manifest, registry, attention_drift
- [x] evaluation: hit rate, AUC, blocked permutation, looks, promote/demote
- [x] scores stored; serve publishes observation / insight; shift offers
- [x] `mufuse interpreters`

Added while building (decision 9): an insight is never shown while a check-in is open, at most one
every 15 minutes, and a check-in asked within 10 minutes after an insight is scored but marked
`after_insight` and left out of the evaluation, since the insight may have shaped the answer.
- [ ] weeks of real use (owner)
