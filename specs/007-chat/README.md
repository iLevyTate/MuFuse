# 007 Chat with a local model (voice later) — design note

**Goal.** The strip opens into a chat. Ask "what are you seeing?" and get a three-part answer: what
changed, how far to trust it, a question back. It also speaks first at four moments. Every number
comes from code; a model only words the answer, and a fixed filter and a fixed crisis path stand
between any model and the person.

**Gate (ROADMAP).** Output-filter test suite (banned phrasings blocked), crisis-path tests, and
fast-loop cues under 1 s (no model in the fast loop). All three run in CI. Voice (speech in and
out) is a follow-up: sherpa-onnx must be 2.0 or later (older builds embed GPL espeak-ng) and its
Python 3.15 wheels are not checked yet.

Constitution 1.2.0 advises full rigour where a wrong output can harm a person. Here that is the
filter and the crisis path: both are plain code with their own test suites, no model can change
them, and every change to them goes through review with those suites.

## What it delivers

- `src/mufuse/chat/crisis.py`: crisis wording in what the person writes → a pre-written reply.
- `src/mufuse/chat/filter.py`: what a model wrote is checked before anyone sees it.
- `src/mufuse/chat/summary.py`: the structured summary (numbers from code) and the template answer.
- `src/mufuse/chat/models.py`: adapters — Ollama on this computer (default), the Claude API
  (opt-in, optional extra `mufuse[cloud]`), and none (templates).
- `src/mufuse/chat/session.py`: one conversation: crisis → summary → model → filter → reply, with
  the late-night limit and the "park this" rule.
- `mufuse serve`: command `ask` (reply returned and published as a `chat` message), `cloud` on/off,
  and `chat` messages at the four moments. `mufuse chat`: a terminal chat with a running engine.

## Decisions (defaults taken; change them here first)

1. **Order of a turn.** Crisis check on the person's words first; if it matches, the fixed reply,
   and nothing goes to any model. Otherwise: summary → model → filter → reply. If the filter
   blocks, or no model answers, the template answer is sent instead and the reply says so.
2. **Crisis reply** (United States first, the owner's country; other countries get the
   international directory): 988 Suicide & Crisis Lifeline (call or text 988), 911 in an
   emergency, findahelpline.com elsewhere. It is the same text every time and never reworded.
3. **Filter blocks**: "you are / you're / you seem / you feel / you sound / you must be" with a
   state or trait word; names of conditions (depression, ADHD, PTSD, disorder, …); diagnosis words
   ("diagnose", "abnormal", "symptom"); treatment advice (medication, "see a doctor/therapist");
   accuracy claims ("accurately detects", "clinically", "medical-grade", "100%"); mind reading
   ("you are thinking", "I can tell what you"). Based on the FDA general-wellness guidance (US).
4. **Summary only.** The model gets the summary (signal quality, baseline words, active
   observations, the last check-in answer) and the person's words, never raw signal or
   recordings. Same for the cloud model.
5. **Models.** Ollama at 127.0.0.1:11434, model `llama3.2` (env `MUFUSE_OLLAMA_MODEL`). Cloud is
   off by default; switched on with `mufuse chat --cloud` / the `cloud` command; uses the official
   `anthropic` SDK, model `claude-opus-5-5` (env `MUFUSE_CLAUDE_MODEL`), low effort, server-side
   refusal fallbacks on. Every reply carries `cloud: true|false` so the strip can show the badge.
   Cloud fails → local; local fails → template.
6. **Speaks first** (templates, no model): session start (signal check), after a check-in answer
   (an acknowledgement, no interpretation), when an observation starts (unless snoozed), at the
   end (counts of check-ins and observations).
7. **After a heavy answer** (grief, loss, panic, worry, "can't cope", …) it stops asking back and
   offers "park this for later". **Late at night** (23:00–05:00 local) at most 20 replies an hour;
   past that, a fixed "it's late, park this for later" reply.
8. **Fast loop.** Check-ins, tones and observations never wait for a model; `ask` runs outside the
   engine's lock, so a slow model never holds up a step.

## Constitution Check

I: local model by default; cloud opt-in, summary only, badge on every cloud reply. II: the filter.
III: the deterministic crisis path. VI: model in the slow loop only.

## Open questions

- Which country's crisis lines should come first for other users? (config later)
- Which local model words best at an acceptable latency on the owner's machine?

## Done

- [x] crisis path + suite
- [x] filter + suite
- [x] summary and template
- [x] model adapters (Ollama, Claude opt-in, none)
- [x] session rules (heavy answer, late night)
- [x] serve `ask` / `cloud` / `chat` messages; `mufuse chat`
- [ ] the strip's chat panel (005b app, next)
- [ ] voice (follow-up)
