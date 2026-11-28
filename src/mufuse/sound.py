"""A tone for a wearer whose eyes are closed.

The terminal bell is only a request to the terminal, and Windows Terminal may answer it with a
flash or with nothing. On Windows the tone goes to the sound card instead.
"""

from __future__ import annotations

import contextlib
import sys
import threading

TONE_HZ, TONE_MS = 880, 700


def _beep() -> None:
    if sys.platform == "win32":
        import winsound

        # No sound device: the terminal bell is all there is.
        with contextlib.suppress(RuntimeError):
            winsound.Beep(TONE_HZ, TONE_MS)


def tone() -> threading.Thread:
    """Play the tone without holding up the caller: the run loop keeps reading the headband."""
    thread = threading.Thread(target=_beep, name="mufuse-tone", daemon=True)
    thread.start()
    return thread
