"""Every hardware acceptance check of feature 001 in one sitting: see `mufuse.sitting`.

uv run python scripts/hw_acceptance.py                 # the whole sitting
uv run python scripts/hw_acceptance.py H5 F1           # just these
uv run python scripts/hw_acceptance.py --resume        # what the last run did not pass
uv run python scripts/hw_acceptance.py --rejudge RUN   # judge saved sessions again
uv run python scripts/hw_acceptance.py --rehearse      # all of it on the simulator
"""

from __future__ import annotations

import sys
from pathlib import Path

from mufuse.sitting import main

if __name__ == "__main__":
    sys.exit(main(repo=Path(__file__).resolve().parent.parent))
