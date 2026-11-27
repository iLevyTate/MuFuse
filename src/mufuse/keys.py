"""Non-blocking single-key reads from the terminal.

Windows reads the console directly. POSIX terminals switch to cbreak mode while the poller is
open, so keys arrive without Enter and Ctrl+C still interrupts. Anything that is not an
interactive terminal (pipes, CI) never reports a key.
"""

from __future__ import annotations

import os
import sys
from types import TracebackType
from typing import Any


class KeyPoller:
    def __init__(self) -> None:
        self._fd: int | None = None
        self._saved: list[Any] | None = None

    def __enter__(self) -> KeyPoller:
        if sys.platform != "win32" and sys.stdin.isatty():
            import termios
            import tty

            fd = sys.stdin.fileno()
            self._saved = termios.tcgetattr(fd)
            tty.setcbreak(fd)
            self._fd = fd
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if sys.platform != "win32" and self._fd is not None and self._saved is not None:
            import termios

            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)
        self._fd = None
        self._saved = None

    def poll(self) -> str | None:
        """The next pressed key, or None when nothing is waiting."""
        if sys.platform == "win32":
            import msvcrt

            return msvcrt.getwch() if msvcrt.kbhit() else None
        if self._fd is None:
            return None
        import select

        ready, _, _ = select.select([self._fd], [], [], 0)
        if not ready:
            return None
        return os.read(self._fd, 1).decode(errors="ignore") or None
