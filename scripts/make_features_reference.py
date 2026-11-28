"""Write the features reference: the frames features v1 gives for a simulated resting wearer.

    uv run python scripts/make_features_reference.py

It replaces `tests/data/features_reference/frames.json` (simulator data only, no personal data).
Run it when a features change is meant, and raise `FEATURES_VERSION` in
`src/mufuse/features/params.py` in the same commit when any frame changed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # for tests.conftest, which holds the shared rehearsal helper

from tests.features_reference import REFERENCE, reference_frames, to_json  # noqa: E402


def main() -> None:
    frames = reference_frames()
    REFERENCE.parent.mkdir(parents=True, exist_ok=True)
    REFERENCE.write_text(json.dumps(to_json(frames), indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {len(frames)} frames to {REFERENCE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
