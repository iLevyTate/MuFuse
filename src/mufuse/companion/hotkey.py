"""A global hotkey that drops a mark while `mufuse serve` runs (005c), from any window.

Windows only for now: `RegisterHotKey` on a thread of its own with its own message loop (a
hotkey belongs to the thread that registered it). Elsewhere `start()` says it is not available
and serve goes on without it; the strip's mark button and the terminal keys still work.
"""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass

DEFAULT = "ctrl+alt+m"

# Win32 modifier flags (MOD_NOREPEAT: holding the keys down marks once)
_MODS = {"alt": 0x0001, "ctrl": 0x0002, "shift": 0x0004, "win": 0x0008}
MOD_NOREPEAT = 0x4000
_NAMED = {f"f{n}": 0x6F + n for n in range(1, 13)} | {"space": 0x20}
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012
_ID = 0x4D46  # "MF"


@dataclass(frozen=True)
class Combo:
    modifiers: int  # Win32 MOD_* flags, without MOD_NOREPEAT
    key: int  # Win32 virtual-key code
    text: str  # as the person wrote it, normalised: "ctrl+alt+m"


def parse(spec: str) -> Combo:
    """`ctrl+alt+m`, `ctrl+shift+f9`, ...: at least one modifier and exactly one key."""
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    mods = [p for p in parts if p in _MODS]
    keys = [p for p in parts if p not in _MODS]
    if len(keys) != 1 or not mods or len(set(mods)) != len(mods):
        raise ValueError(f"--hotkey {spec!r}: one or more of ctrl/alt/shift/win, then one key")
    key = keys[0]
    if len(key) == 1 and (key.isascii() and key.isalnum()):
        vk = ord(key.upper())
    elif key in _NAMED:
        vk = _NAMED[key]
    else:
        raise ValueError(f"--hotkey {spec!r}: the key must be a letter, a digit, f1-f12 or space")
    flags = 0
    for m in mods:
        flags |= _MODS[m]
    order = [m for m in ("ctrl", "alt", "shift", "win") if m in mods]
    return Combo(flags, vk, "+".join([*order, key]))


class Hotkey:
    """Calls `on_press` (on the hotkey's own thread) each time the combination is pressed."""

    def __init__(self, combo: Combo, on_press: Callable[[], None]) -> None:
        self.combo = combo
        self._on_press = on_press
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._ready = threading.Event()
        self._error: str | None = None

    def start(self, timeout: float = 2.0) -> str | None:
        """Register the hotkey. Returns None when it works, else why not (serve goes on)."""
        if sys.platform != "win32":
            return "the global hotkey works on Windows only for now"
        self._thread = threading.Thread(target=self._loop, name="mufuse-hotkey", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout):
            return "the hotkey thread did not start"
        return self._error

    def stop(self) -> None:
        if self._thread is None or sys.platform != "win32":
            return
        import ctypes

        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        self._thread.join(timeout=2.0)
        self._thread = None

    def _loop(self) -> None:  # pragma: no cover - needs a Windows desktop session
        if sys.platform != "win32":  # never reached elsewhere; tells the type checker so
            return
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()
        mods = self.combo.modifiers | MOD_NOREPEAT
        if not user32.RegisterHotKey(None, _ID, mods, self.combo.key):
            self._error = f"{self.combo.text} is taken by another program; no global hotkey"
            self._ready.set()
            return
        self._ready.set()
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY and msg.wParam == _ID:
                    self._on_press()
        finally:
            user32.UnregisterHotKey(None, _ID)
