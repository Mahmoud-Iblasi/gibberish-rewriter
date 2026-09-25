"""Asks the foreground window to switch layout, and falls back to Win+Space.

Mirrors ``csharp/src/GibberishRewriter.App/Win/LayoutSwitcher.cs``.
"""

from __future__ import annotations

from collections.abc import Callable

from gibberish_rewriter.win import foreground, hkl, win32
from gibberish_rewriter.win.input_sender import InputSender

CHECK_DELAY_MS = 200


def needs_win_space(current: int, target: int, installed_count: int) -> bool:
    """Win+Space cycles through the layouts, so it reaches the target for sure only when exactly two are
    installed."""
    return current != target and installed_count == 2


class LayoutSwitcher:
    """Called only from the action thread."""

    def __init__(
        self, sender: InputSender, log: Callable[[str], None], sleep: Callable[[int], None]
    ) -> None:
        self._sender = sender
        self._log = log
        self._sleep = sleep

    def switch(self, target: int) -> None:
        win32.PostMessage(
            win32.GetForegroundWindow(), win32.WM_INPUTLANGCHANGEREQUEST, 0, hkl.to_handle(target)
        )
        self._sleep(CHECK_DELAY_MS)
        current = hkl.low32(foreground.layout_of(win32.GetForegroundWindow() or 0))
        if current == target:
            self._log(f"Switched the layout to {hkl.format(target)}")
        elif needs_win_space(current, target, win32.GetKeyboardLayoutList(0, None)):
            self._sender.win_space()
            self._log(f"The layout stayed {hkl.format(current)}; sent Win+Space")
        else:
            self._log(
                f"The layout stayed {hkl.format(current)}; couldn't switch to {hkl.format(target)}"
            )
