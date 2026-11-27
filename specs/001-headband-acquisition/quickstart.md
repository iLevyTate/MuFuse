# Quickstart: 001 Acquisition

```bash
uv sync
uv run mufuse stream --source sim            # no hardware
uv run mufuse devices                        # headband on, official Muse app closed
uv run mufuse record --notes "first test" --duration 120   # space = moment marker, 1-9 = block markers, q = stop
uv run mufuse inspect recordings/<session_id>
uv run pytest -m "not hardware"              # CI suite
uv run pytest -m hardware -s                 # with headband on
```

## Hardware acceptance (SC-001 to SC-005)

```bash
uv run python scripts/hw_acceptance.py --rehearse --h4-seconds 30   # dry run on the simulator
uv run python scripts/hw_acceptance.py                # the one sitting: headband on, Muse app closed
uv run python scripts/hw_acceptance.py --resume       # only what that run has not passed
uv run python scripts/hw_acceptance.py --rejudge RUN  # judge its saved sessions again, no headband
```

The sitting takes about 27 minutes; the checks that need hands come first. It ends with a report
(`acceptance/<run id>/report.md` in the log folder) that holds nothing personal: that text goes
into the pull request. Sessions, `acceptance.jsonl` and the terminal output do not. The desk
checklist, the timeline and what each check asks are in `tests/hardware/README.md`.
