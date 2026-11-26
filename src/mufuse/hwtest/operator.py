"""The person doing the test: who reads the directions and carries them out.

`HumanOperator` prints directions and waits for the real person. The simulated operator in
`mufuse.hwtest.simulated` prints the same directions and carries them out itself, so the whole
guided run is exercised in CI and can be previewed without a headband (`--dry-run`).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from enum import StrEnum
from typing import Protocol

from rich.console import Console

from mufuse.banner import PHOSPHOR_AMBER
from mufuse.hwtest.checks import CheckResult
from mufuse.keys import KeyPoller

SCOPE_GREEN = "#22C55E"  # docs/BRAND.md: passing checks
CLIP_RED = "#EF4444"  # docs/BRAND.md: failures

KeyReader = Callable[[], str | None]


class Action(StrEnum):
    """Things the guided test asks the person to do."""

    POWER_OFF = "power_off"
    POWER_ON = "power_on"
    PRESS_SPACE = "press_space"
    PRESS_CTRL_C = "press_ctrl_c"
    REST = "rest"
    BLINK = "blink"
    CLENCH = "clench"
    LIFT_TP9 = "lift_tp9"
    RELAX = "relax"


class Operator(Protocol):
    def heading(self, number: int, total: int, title: str, about: str) -> None: ...

    def say(self, text: str, *, wrap: bool = True) -> None:
        """Plain text; `wrap=False` keeps long paths on one line so they can be copied."""
        ...

    def instruct(self, text: str) -> None:
        """A direction to act on right now (highlighted, with a terminal bell)."""
        ...

    def progress(self, text: str) -> None: ...

    def countdown(self, seconds: int, label: str) -> None: ...

    def wait_for_enter(self, prompt: str = "Press Enter to start") -> None: ...

    def act(self, action: Action) -> None:
        """Called right after the matching direction. A person does it; a simulation does it."""
        ...

    def show_result(self, result: CheckResult) -> None: ...

    def capture_keys(self) -> AbstractContextManager[KeyReader]:
        """While open, the returned function reports pressed keys without Enter."""
        ...


class HumanOperator:
    def __init__(self, console: Console, *, sleep: Callable[[float], None] = time.sleep) -> None:
        self.console = console
        self._sleep = sleep

    def heading(self, number: int, total: int, title: str, about: str) -> None:
        self.console.print()
        self.console.rule(f"[bold]Step {number} of {total} · {title}[/bold] [dim]({about})[/dim]")

    def say(self, text: str, *, wrap: bool = True) -> None:
        self.console.print(text, soft_wrap=not wrap)

    def instruct(self, text: str) -> None:
        self.console.bell()
        self.console.print(f"[bold {PHOSPHOR_AMBER}]▶ {text}[/]")

    def progress(self, text: str) -> None:
        self.console.print(f"  {text}", style="dim")

    def countdown(self, seconds: int, label: str) -> None:
        if seconds <= 0:
            return
        self.console.print(f"{label} ", end="")
        for remaining in range(seconds, 0, -1):
            self.console.print(f"{remaining}… ", end="")
            self._sleep(1.0)
        self.console.print()

    def wait_for_enter(self, prompt: str = "Press Enter to start") -> None:
        try:
            self.console.input(f"[bold]{prompt}[/bold] ")
        except EOFError:  # no interactive input (piped): carry on
            self.console.print()

    def act(self, action: Action) -> None:
        return None  # the person does it

    def show_result(self, result: CheckResult) -> None:
        colour = {"pass": SCOPE_GREEN, "fail": CLIP_RED}.get(result.status, "")
        label = result.status.upper()
        style = f"bold {colour}" if colour else "bold"
        self.console.print(f"[{style}]{label}[/]  {result.title}: {result.measured}")

    @contextmanager
    def capture_keys(self) -> Generator[KeyReader]:
        with KeyPoller() as keys:
            yield keys.poll
