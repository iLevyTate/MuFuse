# MuFuse brand

One source of truth for the CLI, docs and the future Flutter app. Direction: **Scientific
Modernism**, read as a lab instrument rather than a wellness app.

## Name and tagline

- **Name:** `MuFuse`. Always one weight and one colour. Never style `Mu` differently from
  `Fuse`; that keeps clear distance from InteraXon's "Muse" trademark.
- **Tagline:** `Punk EEG.`
- "Works with Muse S Athena" is fine as a compatibility statement. Nothing should suggest an
  official Muse product.

## Logo: Concept 7J-3, single-line impulse-to-μ trace

One continuous trace: a horizontal lead-in, a small pre-bump, then a sharp Phosphor Amber impulse
(the "something shifted" moment) that hands off to a Bench Paper lowercase `μ` (mu rhythm, µV)
and settles into a flat resting baseline.

| Asset | Use |
|---|---|
| [`assets/mufuse-banner-dark.svg`](../assets/mufuse-banner-dark.svg) | README and banners on dark backgrounds (transparent) |
| [`assets/mufuse-banner-light.svg`](../assets/mufuse-banner-light.svg) | Same on light backgrounds; μ, baseline and text in Carbon |
| [`assets/mufuse-icon.svg`](../assets/mufuse-icon.svg) | 1:1 app icon and favicon on Lab Slate with a Graticule grid; checked at 16×16 px |
| `src/mufuse/banner.py` | Terminal version as a plain-ASCII line trace (slashes, underscores, pipes), 5 lines × 80 columns |

Construction rules:
- The colour change happens at the μ's left stem. Amber is never used to the right of it.
- The μ stroke is heavier than the trace (8 vs 5 in the banner) so the letter reads at small sizes.
- Round caps and joins throughout. No gradients, glows or drop shadows.
- Leave clear space of at least the μ's height around the mark.

## Palette

| Token | Hex | Role |
|---|---|---|
| `lab-slate` | `#111315` | Primary dark canvas |
| `bench-paper` | `#F3F1EC` | Primary light canvas; the resting trace and μ on dark |
| `carbon` | `#181A1C` | Ink on light |
| `graticule` | `#2A2F36` | 1 px borders, plot gridlines |
| `phosphor-amber` | `#F59E0B` | Active shift cue, impulse spike, primary accent |
| `scope-green` | `#22C55E` | Good electrode contact, stream lock, passing checks |
| `clip-red` | `#EF4444` | Dropped packets, poor contact, motion artifact |

Status colours describe **signal quality only** (contact, packets, artifacts). Never use them to
grade a person's state: there is no "red = bad mood".

The light banner's tagline uses a darker amber (`#B45309`) so the text stays readable on white.
The mark itself always uses `phosphor-amber`. The one exception is the CLI banner, which draws the
impulse in orange (`#F97316`) and the μ and baseline in white (`#FFFFFF`) so the ASCII trace reads
clearly in a terminal.

## Typography (SIL Open Font License)

- **IBM Plex Mono:** headings, CLI, telemetry, numbers.
- **IBM Plex Sans:** body prose and journal text.

SVG text falls back to `ui-monospace, Menlo, Consolas, monospace` where Plex isn't installed.

## Voice

Curious, warm, plain-spoken, a little rebellious. Confident about the data, humble about the
meaning. See constitution principle II, *Describe, Don't Label*.

- Describe signals and how confident we are, compared with *your* baseline: "Heart rate up 12
  bpm and blinks doubled vs this morning (fair signal quality). What was going on?"
- Never label mental states ("you're anxious", "you're stressed").
- Never make clinical or mind-reading claims ("clinically proven", "we decoded your thoughts").
- Medical or crisis topics follow the fixed safety path, not brand voice.

## Required notice

Wherever the product is described publicly:

> MuFuse is an independent, MIT-licensed open-source project and is not affiliated with, endorsed
> by, or sponsored by InteraXon Inc. Muse is a trademark of InteraXon Inc.
