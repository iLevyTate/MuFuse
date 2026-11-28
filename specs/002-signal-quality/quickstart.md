# Quickstart: 002 Signal Quality

## Without a headband (SC-005 to SC-010, and the rehearsed gate)

```bash
uv sync
uv run pytest -m "not hardware"            # every rule, replay identity, ear independence, wording, speed
uv run mufuse stream --source sim          # quality block under the sensor panel
uv run mufuse record --source sim --duration 30 --out /tmp/q
uv run mufuse inspect /tmp/q/<session>     # ends with "Signal quality (rules 1)"
uv run mufuse quality label --source sim --out /tmp/q   # scripted wearer follows the cues; 9.5 min, real time
uv run mufuse quality score /tmp/q/<session>            # the report again (replay: not checked), exit 0
```

Expected: the tests pass in under 2 minutes with coverage at 80% or above; the rehearsed session scores 20 of 20
for each kind, 10 of 10 lifts and "replay identical to live". CI runs the same rehearsal on a fake clock in seconds
(`tests/integration/test_quality_gate.py`). A green rehearsal proves the pipeline, not the physiology.

Rules change? `uv run python scripts/make_quality_reference.py` rewrites `tests/data/quality_reference/answers.json`;
raise `RULES_VERSION` in the same commit when any answer changed.

## Public set (SC-003)

```bash
uv run python scripts/fetch_muse2_set.py            # 400 MB, to the user cache folder, checksum checked
uv run mufuse quality score --public <printed folder>
```

On 2026-11-27 the scripted download worked and the checksum matched. Rules v1 scores 70.6% of the blinks and
22.7% of the jaw clenches there, under the 90% of SC-003 (research R12, R13); the clench task is inferred from
the data.

If the download is refused, fetch `sourcedata.zip` in a browser from
https://doi.org/10.6084/m9.figshare.30162868.v1 and run `scripts/fetch_muse2_set.py --from <file>`. The set is
CC BY 4.0 (Lee and Ahn) and never enters the repo.

## Headband sitting (SC-001, SC-002, SC-004, and SC-005 on the device)

Two sittings of about 10 minutes each. The first was recorded on 2026-11-27 (research R17); the limits were
checked on it and frozen as rules v1 without a change (R13), so its score is information, not the gate. The
second, recorded after the freeze, is the gate (T061). Anyone else with an Athena needs one sitting only.
Headband on and awake, phone Muse app closed, in the user's own PowerShell window:

```powershell
uv run mufuse quality label --source athena
```

Follow the screen: sit still, eyes open, eyes closed until the bell, then 20 blinks, 20 jaw clenches, 20 head
turns and 10 sensor lifts on cue. The command ends with the score report. The recording stays in `recordings/`
(git-ignored); only the report's numbers go into the pull request.

A fail is reported as a fail. If the rules are changed afterwards, they become a new rules version and the sitting
is repeated; the 90% limit is not lowered. Ear sensors that are out (issue #12) do not fail anything here: coverage
`reduced` is a usable session.

## Where the details are

- Exact rules: [contracts/quality-rules.md](./contracts/quality-rules.md)
- What other features read: [contracts/quality-interface.md](./contracts/quality-interface.md)
- Screens, texts, exit codes: [contracts/cli.md](./contracts/cli.md)
- Cues and scoring: [contracts/labelled-session.md](./contracts/labelled-session.md)
- Entities: [data-model.md](./data-model.md)
