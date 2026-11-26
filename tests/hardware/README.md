# Hardware acceptance checklist: 001 acquisition

Run with the headband on, the Muse app closed, and the PC within 2 m. Record results in the PR.

| # | Check | How | Pass |
|---|---|---|---|
| H1 | Discovery (T016) | `uv run pytest -m hardware -s -k discoverable` | Headband listed |
| H2 | All streams (T017) | `uv run pytest -m hardware -s -k streams` | Each stream ≥ 95% of nominal samples over 30 s |
| H3 | SC-001 time to signal | `uv run mufuse stream`, time from command to live EEG, 10 attempts | ≤ 15 s in ≥ 9/10 |
| H4 | SC-002 completeness | `uv run mufuse record --duration 600`, then `inspect` | Every stream ≥ 99.5% complete |
| H5 | SC-003 dropout recovery | During `record`, power the headband off for 10 s, then on | Streaming resumes ≤ 20 s; `inspect` shows one gap ≈ 10 s (±0.5 s) |
| H6 | SC-004 markers | Press `space` 3× during `record` | 3 markers in `inspect` |
| H7 | SC-005 interruption | Ctrl+C mid-recording | `inspect` reads it as finalized |
| H8 | Channel check sanity | During `stream`: lift one sensor, clench jaw, blink | Lifted → `flat`/`railed`; clench → `noisy` on TP9/TP10; blinks stay `ok` |

H8 is how to tune the thresholds in `src/mufuse/acquisition/signal_check.py`.
