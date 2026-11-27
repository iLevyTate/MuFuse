# Quality reference recording

The files beside this one are made by the simulator. They hold no personal data.

- `session/`: a short simulated session with every contact fault and every disturbance.
- `answers.json`: the answers of the quality rules for that session.

Both are rewritten only by `scripts/make_quality_reference.py`. A test compares the rules with
`answers.json`, so a change that alters an answer is seen. When an answer changes, raise
`RULES_VERSION` in `src/mufuse/quality/rules.py` in the same commit.
