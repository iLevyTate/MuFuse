# 007b Voice: speak to the chat, hear the reply — design note

**Goal.** `mufuse chat --voice`: press Enter, say the question, hear the answer. Speech in and out
on this computer only, through sherpa-onnx (Apache-2.0, 2.0 or later). Voice replaces the keyboard
and the screen and nothing else: the words heard go to the engine's `ask` exactly as typed words
do, so the crisis path and the output filter (007) stand between any model and the person
unchanged.

**Gate.** In CI, with fake microphone, recogniser and voice: a spoken turn reaches `ask` as text,
the reply is spoken and printed, the crisis reply is printed even when speech fails, and the voice
path opens no socket but the engine's own on 127.0.0.1 (prior-art survey 3.8, egress checklist).
On the owner's machine, `mufuse voice check` reports how long hearing and speaking take
(survey open question: which models meet the 1 s budget).

## What it delivers

- `src/mufuse/voice/models.py`: the pinned model files (URL, sha256, licence), `mufuse voice
  fetch` (the only step that touches the network), where they live (`<user data>/Models`).
- `src/mufuse/voice/listen.py`: the microphone at 16 kHz, Silero VAD ends a turn, the recogniser.
- `src/mufuse/voice/speak.py`: text to speech and playback.
- `src/mufuse/voice/turn.py`: one voice turn, with every part injected (tests use fakes).
- `mufuse chat --voice`, `mufuse voice fetch`, `mufuse voice check`.
- Optional extra `mufuse[voice]`: `sherpa-onnx>=2.0.3`, `sounddevice>=0.5.6` (MIT; PortAudio).

## Decisions (defaults taken; change them here first)

1. **Push to talk.** Enter starts listening; the turn ends after 0.8 s of silence (VAD) or 20 s;
   an empty line (Enter on nothing heard twice, or typing `q`) ends the chat. The microphone is
   open only while listening. Typing still works: anything typed instead of Enter is sent as text.
2. **Nothing kept.** Audio stays in memory and is dropped after the turn; it is never written to
   disk or recorded with a session. The transcript is shown ("heard: …") so the person sees what
   was understood, and goes to `ask` like typed words.
3. **Models**, all fetched by `mufuse voice fetch`, checked by sha256, never downloaded silently:
   - VAD: Silero VAD (`silero_vad.onnx`, MIT).
   - Hearing: Moonshine base English, quantized (2026-02-27, MIT, 111 MB); `--small` uses Moonshine
     tiny English (29 MB) where base is too slow.
   - Speaking: Pocket TTS int8 (2026-01-26, CC-BY-4.0, 98 MB), in the voice of the package's first
     reference recording. It has its own text front end, so no word is skipped: Kitten nano
     (Apache-2.0, lexicon) was tried and dropped "988", "or", "42" and "RMSSD" as unknown words,
     which rules it out while the crisis reply is spoken. Attribution: Kyutai, in `docs/NOTICES.md`.
   - Numbers to call or text are spoken digit by digit ("call or text nine eight eight"): read as
     "988" the round trip came back "908"; spelled, it comes back "988".
4. **Crisis.** The crisis reply is printed in full before anything is spoken, and printing never
   waits for speech. If speaking fails, the text stands.
5. **No network.** `HF_HUB_OFFLINE=1` and `HF_HUB_DISABLE_TELEMETRY=1` are set before sherpa-onnx is
   imported; a test fails if a voice turn opens a non-loopback socket.
6. **Not built here.** The strip's own microphone button (Phase 1, 013 uses the same engine in
   Dart), a wake word, barge-in (talking over the reply), the voice journal (008 follow-up).

## Constitution Check

I: local only, audio never stored, models fetched once by an explicit command with checksums.
II/III: the transcript goes through `ask`, so filter and crisis path are unchanged. VI: speech
models in the slow loop only; check-ins and tones never wait for them.

## What was found (2026-11-28, owner's laptop ON BATTERY at 20%, so throttled)

- Moonshine base: 3.8 s of speech written down in 0.31 s (once, unthrottled moments) to 4.3 s
  (throttled). Tiny: 0.10 s. Both word-perfect on the package's test recording.
- Pocket TTS: real-time factor about 8 throttled (36 s for 4.5 s of speech). Kitten nano was about 4
  in the same state. These figures are not the machine's; `mufuse voice check` plugged in decides.
- Round trip (Pocket speaks, Moonshine writes back): 100% of the check phrase; the crisis lines
  come back right once numbers are spelled.
- Moonshine once repeated a short sentence three times ("call 911 and if there is immediate
  danger, call 911 and …"), a known habit of the model on short clips. The transcript is always
  shown ("heard: …"), so the person sees what was understood before the reply.
- "I want to end it" (without "all") does not match the crisis patterns. Not changed here: the
  patterns are 007's, under full rigour, and need the owner's word.

## Open questions

- Is Moonshine base fast enough on the owner's CPU (`mufuse voice check`), or should tiny be the
  default?
- Is Pocket TTS fast enough plugged in? If not: speak sentence by sentence (the first plays while
  the next is rendered), or Supertonic (own text front end; OpenRAIL licence to read first).

## Done

- [x] models + fetch (pinned sha256, unpacked with the tar `data` filter)
- [x] listen / speak / turn with fakes; a real round trip runs where the models are fetched
- [x] `mufuse chat --voice`, `mufuse voice fetch|check`
- [x] egress test (a voice chat turn connects to 127.0.0.1 only; the real round trip to nothing)
- [ ] `voice check` on the owner's machine, plugged in (owner)
