"""Everything Engine asks of Windows, plus the notification texts both apps share."""

from __future__ import annotations

import enum
import typing
from collections.abc import Collection
from dataclasses import dataclass

from .key_table import LayoutKind

ADMINISTRATOR_WINDOW = (
    "Can't fix text in an administrator window. Run Gibberish Rewriter as administrator to allow it."
)
"""Notification shown when the foreground window is elevated and this app is not."""

CLIPBOARD_BUSY = "Couldn't use the clipboard because another app is holding it. Try again."
"""Notification shown when the clipboard stays locked by another app."""


class Shortcut(enum.Enum):
    """Shortcuts Engine sends. The platform picks console variants."""

    COPY = "copy"
    PASTE = "paste"
    UNDO = "undo"


@dataclass(frozen=True)
class ForegroundWindow:
    """The foreground window when an action runs. layout is None outside the pair."""

    window: int
    layout: LayoutKind | None
    is_console: bool
    is_blocked_by_elevation: bool


class ClipboardUnavailableError(Exception):
    """Raised by clipboard calls when another app keeps the clipboard open after every retry."""

    def __init__(self, message: str) -> None:
        """The message is required, as it is on the C# ClipboardUnavailableException."""
        super().__init__(message)


@typing.runtime_checkable
class Platform(typing.Protocol):
    """Everything Engine asks of Windows. Called only from the action thread."""

    def wait_for_release(self, vks: Collection[int], timeout_ms: int) -> bool:
        """Waits until none of the keys is physically down. False if one still is after the timeout. CapsLock and
        the trigger are swallowed, so Windows' key state never shows them down: the platform tracks them from the
        hook."""
        ...

    def send_backspaces(self, count: int) -> None: ...

    def type_text(self, text: str) -> None: ...

    def send_shortcut(self, shortcut: Shortcut) -> None: ...

    def save_clipboard(self) -> object: ...

    def restore_clipboard(self, saved: object) -> None: ...

    def clipboard_sequence(self) -> int: ...

    def read_clipboard_text(self) -> str | None: ...

    def set_clipboard_text(self, text: str) -> None: ...

    def switch_layout(self, layout: LayoutKind) -> None: ...

    def foreground_info(self) -> ForegroundWindow: ...

    def sleep(self, milliseconds: int) -> None: ...

    def notify(self, message: str) -> None: ...
