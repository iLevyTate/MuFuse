"""CLI header: the Concept 7J-3 impulse-to-mu trace drawn in plain ASCII (docs/BRAND.md)."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from rich.console import Console
from rich.text import Text

# CLI only: a punchier orange and pure white than the SVG mark's amber and paper (docs/BRAND.md).
CLI_ORANGE = "#F97316"
CLI_WHITE = "#FFFFFF"

# Lead-in, pre-bump, impulse and dip, then the mu settling into its resting baseline. Plain ASCII
# so every terminal font draws it. Columns before MU_COLUMN (the mu's left stem) are orange.
_TRACE = (
    r"            /\                            ",
    r"           /  \       |   |               ",
    r" ____/\___/    \  /\__|___|_______________",
    r"                \/    |                   ",
    r"                      |                   ",
)
MU_COLUMN = 22
HEIGHT_LINES = len(_TRACE)
MAX_WIDTH = 80
_GAP = "  "


def _version() -> str:
    try:
        return version("mufuse")
    except PackageNotFoundError:
        return "dev"


def render_banner(status: str = "") -> Text:
    """The mark on the left; name, version, tagline and `status` beside it."""
    info = [f"MuFuse v{_version()}", "Punk EEG.", "", status]
    room = MAX_WIDTH - len(_TRACE[0]) - len(_GAP)
    out = Text()
    for line, row in enumerate(_TRACE):
        out.append(row[:MU_COLUMN], style=CLI_ORANGE)
        out.append(row[MU_COLUMN:], style=CLI_WHITE)
        label = info[line - 1] if 0 < line <= len(info) else ""
        if label:
            label = label if len(label) <= room else label[: room - 1] + "…"
            out.append(_GAP)
            out.append(label, style="bold" if line == 1 else ("dim" if line == 2 else ""))
        out.append("\n")
    out.rstrip()
    return out


def print_banner(console: Console, status: str = "") -> bool:
    """Print the header for people, not pipes: skipped unless output is an interactive terminal.

    Returns whether it was printed.
    """
    if not console.is_terminal:
        return False
    console.print(render_banner(status))
    return True
