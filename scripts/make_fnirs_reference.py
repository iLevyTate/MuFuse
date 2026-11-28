"""Write the fNIRS reference: what fnirs v1 gives for two simulated minutes.

    uv run python scripts/make_fnirs_reference.py

It replaces `tests/data/fnirs_reference/hemo.json` (simulator data only, no personal data).
Run it when a pipeline change is meant, and raise `FNIRS_VERSION` in `src/mufuse/fnirs/mbll.py`
in the same commit when any value changed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # for tests.conftest, which holds the shared rehearsal helper

from tests.fnirs_reference import REFERENCE, reference_hemo, to_json  # noqa: E402


def main() -> None:
    hemo = reference_hemo()
    REFERENCE.parent.mkdir(parents=True, exist_ok=True)
    REFERENCE.write_text(json.dumps(to_json(hemo)) + "\n", encoding="utf-8")
    print(f"Wrote {hemo.t.size} samples (every 32nd kept) to {REFERENCE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
