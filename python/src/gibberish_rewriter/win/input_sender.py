"""SendInput. Every event carries ``input_builder.EXTRA_INFO``.

Mirrors ``csharp/src/GibberishRewriter.App/Win/InputSender.cs``.
"""

from __future__ import annotations

import ctypes
from collections.abc import Callable

from gibberish_rewriter.core.platform import Shortcut

from gibberish_rewriter.win import input_builder, win32
from gibberish_rewriter.win.win32 import INPUT


class InputSender:
    """Sends keyboard input with SendInput. Called only from the action thread."""

    def __init__(self, log: Callable[[str], None]) -> None:
        self._log = log

    def key_press(self, vk: int) -> None:
        self._send(input_builder.key_press(vk))

    def backspaces(self, count: int) -> None:
        self._send(input_builder.backspaces(count))

    def text(self, text: str) -> None:
        self._send(input_builder.text(text))

    def shortcut(self, shortcut: Shortcut, console: bool) -> None:
        self._send(input_builder.shortcut(shortcut, console))

    def win_space(self) -> None:
        self._send(input_builder.win_space())

    def _send(self, events: list[INPUT]) -> None:
        for event in events:
            # Virtual-key events also get their scan code; some apps read it instead of the virtual key.
            if not event.u.ki.dwFlags & win32.KEYEVENTF_UNICODE:
                event.u.ki.wScan = win32.MapVirtualKey(event.u.ki.wVk, win32.MAPVK_VK_TO_VSC)
        for chunk in input_builder.chunks(events):
            block = (INPUT * len(chunk))(*chunk)
            sent = win32.SendInput(len(chunk), block, win32.INPUT_SIZE)
            if sent != len(chunk):
                error = ctypes.get_last_error()
                self._log(f"SendInput sent {sent} of {len(chunk)} events (error {error})")
