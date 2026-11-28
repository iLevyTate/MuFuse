"""A tone for a wearer whose eyes are closed, on any computer.

The terminal bell is only a request to the terminal, and many terminals answer it with a flash
or with nothing. The tone goes to the sound card instead: a short sine wave made here, played by
`winsound` on Windows and by the system's own player elsewhere (`afplay` on macOS; `paplay`,
`pw-play` or `aplay` on Linux). No player, no sound card: the bell is all there is.
"""

from __future__ import annotations

import contextlib
import io
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import wave
from collections.abc import Callable
from functools import cache

TONE_HZ, TONE_MS = 880, 700
RATE_HZ = 22_050
FADE_MS = 15  # a hard start or stop clicks
PLAYER_TIMEOUT_S = 5.0

# In the order they are tried: the sound servers of current desktops first, ALSA's own last.
_PLAYERS: dict[str, tuple[tuple[str, ...], ...]] = {
    "darwin": (("afplay",),),
    "other": (("paplay",), ("pw-play",), ("aplay", "-q")),
}


@cache
def tone_wav() -> bytes:
    """The tone as a 16-bit mono WAV file, faded in and out."""
    n, fade = RATE_HZ * TONE_MS // 1000, RATE_HZ * FADE_MS // 1000
    frames = bytearray()
    for i in range(n):
        gain = min(1.0, i / fade, (n - 1 - i) / fade)
        frames += struct.pack(
            "<h", round(0.5 * 32767 * gain * math.sin(2 * math.pi * TONE_HZ * i / RATE_HZ))
        )
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE_HZ)
        w.writeframes(bytes(frames))
    return out.getvalue()


def player(platform: str, which: Callable[[str], str | None] = shutil.which) -> list[str] | None:
    """The command that plays a WAV file on this system (the file goes last), if there is one."""
    for name, *args in _PLAYERS["darwin" if platform == "darwin" else "other"]:
        if (path := which(name)) is not None:
            return [path, *args]
    return None


def play_with_player(platform: str) -> None:
    """Play the tone through the system's player. Every failure stays here: it is only a tone."""
    command = player(platform)
    if command is None:
        return
    fd, path = tempfile.mkstemp(prefix="mufuse-tone-", suffix=".wav")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(tone_wav())
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(
                [*command, path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=PLAYER_TIMEOUT_S,
                check=False,
            )
    finally:
        with contextlib.suppress(OSError):
            os.remove(path)


def _beep() -> None:
    if sys.platform == "win32":
        import winsound

        # No sound device: the terminal bell is all there is.
        with contextlib.suppress(RuntimeError):
            winsound.PlaySound(tone_wav(), winsound.SND_MEMORY)
    else:
        play_with_player(sys.platform)


def tone() -> threading.Thread:
    """Play the tone without holding up the caller: the run loop keeps reading the headband."""
    thread = threading.Thread(target=_beep, name="mufuse-tone", daemon=True)
    thread.start()
    return thread
