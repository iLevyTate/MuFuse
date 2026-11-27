# Contract: CLI

| Command | Behavior | Exit codes |
|---|---|---|
| `mufuse devices [--timeout 8]` | BLE scan, list Muse devices (name, address, RSSI), mark saved device | 0 found / 3 none |
| `mufuse stream [--source athena\|sim\|play PATH] [--device NAME] [--preset p1041]` | live view until `q`/Ctrl+C | 0 / 2 bad args / 4 connect fail / 130 Ctrl+C while connecting |
| `mufuse record [same opts] [--notes TEXT] [--out DIR] [--duration SEC]` | live view + recording + key markers | 0 / 2 / 4 / 5 write error / 130 |
| `mufuse inspect PATH` | print manifest summary, per-stream rows/rate/completeness, markers, gaps | 0 / 6 unreadable |

Stopping (`q`, Ctrl+C or `--duration`): the session is finalized and its path printed first, then the headband is
released (about 8 s on the real device). Ctrl+C never interrupts either step, and a second Ctrl+C changes nothing.
Ctrl+C once the live view is up exits 0. Ctrl+C while still connecting releases the headband, records nothing and
exits 130. If the recording stops before the signal has returned from a drop, the gap is written with `end: null`.

Before it connects to the headband, `stream` and `record` print one line that says so and how long it usually takes
(about 5 s, up to 20 s if the headband is not found). The simulator connects at once and prints no such line, unless it
plays a rehearsed wearer with the headband's waits.

Output is UTF-8 on every stream, also when piped or redirected.
