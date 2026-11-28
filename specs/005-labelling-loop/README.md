# 005 Labelling loop, `mufuse serve` and the desk strip — design note

**Goal.** Ask the wearer, now and then, what is on their mind, and keep every answer with where
the question came from, so that later features (006) can learn whether a signal shift means
anything for this person. Put the live picture on a small strip at the desk.

**Gate (ROADMAP).** One week of real use: at least 70% of prompts answered, labels stored separately
by source. CI checks everything that can be checked without a person: the 30% random share, the
15-minute spacing, the quiet rules, storage by source, and the served messages against stored
examples. The week of use is the owner's (not a show stopper).

Built as two pull requests: **005a** engine side (this note's decisions 1-8) and **005b** the
Flutter strip (decisions 9-11).

## What it delivers

- `src/mufuse/companion/store.py`: SQLite store (stdlib `sqlite3`) in the user data folder:
  sessions, check-ins (asked, answered, source, answer), marks, the wearer's answer list.
- `src/mufuse/companion/scheduler.py`: when to ask, with an injected clock and random generator.
- `src/mufuse/companion/describe.py`: the "now against your baseline" line, from z-scores, in code.
- `src/mufuse/companion/serve.py` and `mufuse serve`: the engine (acquisition, quality, features,
  scheduler, recording) behind a local HTTP API for the app.
- `app/`: the Flutter desktop strip (005b).

## Decisions (defaults taken; change them here first)

1. **Sources.** Every check-in has one source: `random`, `shift` (asked because a signal shifted;
   006 supplies the shifts, 005 only accepts them) or `self` (the wearer opened it). Hit rates are
   never counted across sources.
2. **Random share.** Random check-ins come at random moments, on average one every 25 minutes
   (an exponential wait, never under the spacing). A `shift` check-in is refused when allowing it
   would bring the random share of the session's asked check-ins under 30%.
3. **Spacing.** At most one asked check-in (random or shift) every 15 minutes; `self` check-ins are
   always allowed and do not reset the spacing.
4. **Quiet.** No asked check-in while the signal is poor (no forehead sensor good), while the head
   is moving, during a snooze (one click = 60 minutes) or during a do-not-disturb focus block.
   A random moment that falls in a quiet time is skipped, not queued.
5. **Answers.** One neutral question, "What's on your mind?", and one-tap answers in a new order each
   time: on task, planning, daydreaming, worry, stuck on a thought, memory, urge, feeling low,
   nothing much, or own words. The list is the wearer's to edit (stored). An unanswered check-in
   expires after 2 minutes and is kept as unanswered (it counts against the 70%).
6. **The baseline line.** Per series with a z-score: |z| < 1 "usual", 1–2 "a little higher/lower",
   ≥ 2 "higher/lower"; heart rate "steady" when usual. Only when the signal is good; otherwise the
   line names the sensor to fix. Words describe the signal, never the person (constitution II).
7. **`mufuse serve`.** HTTP on 127.0.0.1 only, on a free port; a token made fresh each run is
   required on every request. Port and token are written to `serve.json` in the user state folder
   for the app. Engine → app: Server-Sent Events on `GET /events` (`hello`, `status`, `features`,
   `checkin`, `checkin_closed`, `session`), once a second at most for `status` and `features`.
   App → engine: `POST /command` with `mark`, `answer`, `snooze`, `focus`, `checkin` (self).
   Every message carries `"v": 1`; examples are stored in `tests/data/serve_messages/` and checked.
   No new dependency (stdlib `http.server`).
8. **Recording.** `serve` records the session like `mufuse record` does, with every mark and
   check-in also written as a marker, so a session can be replayed with its labels.
9. **The strip** (005b): one always-on-top line: quality dot (signal only, `docs/BRAND.md`), session
   time, the baseline line, and buttons check in / mark / snooze. A check-in opens a small panel.
10. **The app talks only to `mufuse serve`**, through `serve.json`; if the engine is not running it
    says so and shows the command to start it.
11. **App tests** run against stored event streams (`flutter test`), in a separate CI job.

Not in 005a/b: the global hotkey (added as 005c, below) and the BLE ring (the strip's mark button and the terminal keys
stand in), the chat (007), shift detection (006).

## Constitution Check

I: local only, 127.0.0.1, per-run token, store in the user's own data folder, nothing leaves the
machine. II: one neutral question, describe-only baseline words, status colours grade signal only.
V: sources kept apart, random share enforced in code. VI: no model anywhere in 005. VIII: the
served message format is versioned for a later phone engine.

## Open questions

- 25 minutes on average between random check-ins: too many for 90-minute sessions?
- Should an unanswered check-in expire sooner than 2 minutes?

## Done

- [x] store (005a)
- [x] scheduler with injected clock (005a)
- [x] describe line (005a)
- [x] `mufuse serve` with stored message examples (005a)
- [x] Flutter strip and its CI job (005b). Always-on-top comes from each platform's runner:
  `window_manager` 0.6 (MIT) was tried and its native core (cnativeapi) does not compile against
  the Windows SDK here, so the app has no runtime package; the window is a fixed small size
- [x] chat panel on the strip for 007 (replies shown as sent, own lines, cloud switch, a "cloud"
  badge on every cloud reply); `hello` now says whether the cloud model is on
- [x] global hotkey (005c): `mufuse serve --hotkey ctrl+alt+m` (the default; `none` turns it off)
  marks a moment from any window. Windows only for now (`RegisterHotKey` on a thread of its own,
  no new dependency); elsewhere serve says so and goes on. A hotkey mark is stored and recorded
  with source `keyboard`, apart from the strip's `app` marks. A combination another program
  holds is reported, not fatal.
- [ ] a week of real use (owner)
