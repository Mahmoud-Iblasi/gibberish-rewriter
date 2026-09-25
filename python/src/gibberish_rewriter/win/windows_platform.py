"""The Core's Platform on Windows, for one Engine and its layout pair. Called on the action thread.

Mirrors ``csharp/src/GibberishRewriter.App/Win/WindowsPlatform.cs``. ``Platform`` is a runtime-checkable protocol,
so an ``isinstance`` check would pass on method names alone; it is inherited here so a wrong signature is a real
error rather than a call that fails in the middle of a fix (plan decision 9).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Collection

from gibberish_rewriter.core.key_table import LayoutKind
from gibberish_rewriter.core.platform import ForegroundWindow, Platform, Shortcut

from gibberish_rewriter.win import foreground, win32
from gibberish_rewriter.win.clipboard_service import ClipboardService
from gibberish_rewriter.win.hkl import LayoutPair
from gibberish_rewriter.win.input_sender import InputSender
from gibberish_rewriter.win.key_state import KeyStateTracker
from gibberish_rewriter.win.layout_switcher import LayoutSwitcher

RELEASE_POLL_MS = 10


class WindowsPlatform(Platform):
    """Everything Engine asks of Windows, for one layout pair."""

    def __init__(
        self,
        pair: LayoutPair,
        sender: InputSender,
        clipboard: ClipboardService,
        switcher: LayoutSwitcher,
        keys: KeyStateTracker,
        notify: Callable[[str], None],
    ) -> None:
        self._pair = pair
        self._sender = sender
        self._clipboard = clipboard
        self._switcher = switcher
        self._keys = keys
        self._notify = notify

    def wait_for_release(self, vks: Collection[int], timeout_ms: int) -> bool:
        started = time.monotonic()
        while any(self._is_down(vk) for vk in vks):
            if (time.monotonic() - started) * 1000 >= timeout_ms:
                return False
            time.sleep(RELEASE_POLL_MS / 1000)
        return True

    def send_backspaces(self, count: int) -> None:
        self._sender.backspaces(count)

    def type_text(self, text: str) -> None:
        self._sender.text(text)

    def send_shortcut(self, shortcut: Shortcut) -> None:
        self._sender.shortcut(
            shortcut, foreground.is_console_class(foreground.class_name_of(win32.GetForegroundWindow()))
        )

    def save_clipboard(self) -> object:
        return self._clipboard.save()

    def restore_clipboard(self, saved: object) -> None:
        self._clipboard.restore(saved)

    def clipboard_sequence(self) -> int:
        return self._clipboard.sequence()

    def read_clipboard_text(self) -> str | None:
        return self._clipboard.read_text()

    def set_clipboard_text(self, text: str) -> None:
        self._clipboard.set_text(text)

    def switch_layout(self, layout: LayoutKind) -> None:
        self._switcher.switch(self._pair.hkl_of(layout))

    def foreground_info(self) -> ForegroundWindow:
        return foreground.read(self._pair)

    def sleep(self, milliseconds: int) -> None:
        time.sleep(milliseconds / 1000)

    def notify(self, message: str) -> None:
        self._notify(message)

    def _is_down(self, vk: int) -> bool:
        """Swallowed keys show only in the hook's tracker; other keys show in Windows' key state too."""
        return self._keys.is_down(vk) or win32.GetAsyncKeyState(vk) < 0
