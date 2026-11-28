# 008 Journal, timeline and weekly review — design note

**Goal.** Look back: one session as a timeline (check-ins, observations, marks, notes, meetings),
a journal of the wearer's own notes, and a weekly reflection whose patterns are counted in code.

**Gate (ROADMAP).** Every pattern shown has n, an effect and the label "hypothesis". Checked in CI
on every pattern the code can produce, in the terminal and on the review page.

## What it delivers

- Store: `observations` (each start and end, written by `mufuse serve`), `journal` (notes with
  tags), `context` (time windows with a tag, e.g. meetings from a calendar file).
- `src/mufuse/journal/timeline.py`, `patterns.py`, `calendar.py`, `review.py`.
- `mufuse journal add TEXT [--tag T]`, `mufuse journal list`, `mufuse timeline [SESSION]`,
  `mufuse calendar import FILE.ics`, `mufuse review [--days 7] [--out FILE]` (a self-contained
  HTML page in the user data folder; nothing is served or sent).
- `mufuse serve`: command `note` (a journal note from the strip).

## Decisions (defaults taken; change them here first)

1. **Only random check-ins make patterns** (constitution V): shift and self check-ins are shown on
   the timeline but never counted.
2. **Pattern kinds.** (a) After an observation of a kind (e.g. "blink rate higher"), the answers of
   random check-ins asked within 10 minutes of its start; (b) inside a context tag (e.g. meetings)
   against outside it. Each: hits of n, the share, the base rate over all random check-ins of the
   period, the effect in percentage points, and the label "hypothesis".
3. **Shown only from n ≥ 3**, at most 10, largest effect first, with one line saying that many
   patterns are compared and some will be chance.
4. **Calendar** from an `.ics` file the wearer exports (stdlib parser: VEVENT, DTSTART, DTEND,
   SUMMARY; all-day events skipped). Every event is tagged `meeting`; its title stays local. No
   account, no network.
5. **Voice journal** waits for voice (007 follow-up); notes are typed.
6. **Review page** is static HTML with every text escaped, written to the user data folder; status
   colours grade signal quality only.

## Constitution Check

I: everything local, the page is a file. II: patterns describe co-occurrence in the wearer's own
answers and are labelled hypotheses. V: random check-ins only.

## Done

- [x] store tables; serve writes observations and takes notes
- [x] timeline
- [x] patterns with n, effect, "hypothesis" (gate)
- [x] calendar import
- [x] review page and CLI
