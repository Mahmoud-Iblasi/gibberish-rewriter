"""A scripted platform that records the calls vectors can expect (plan Task 10, vector harness rules)."""

from __future__ import annotations

from collections.abc import Callable, Collection
from dataclasses import dataclass

from gibberish_rewriter.core.key_table import LayoutKind
from gibberish_rewriter.core.platform import (
    ClipboardUnavailableError,
    ForegroundWindow,
    Platform,
    Shortcut,
)


@dataclass(frozen=True)
class _SavedClipboard:
    text: str | None


class FakePlatform:
    """A scripted platform that records the calls vectors can expect (plan Task 10, vector harness rules)."""

    def __init__(self) -> None:
        self._clipboard_sequence = 1
        self.calls: list[str] = []
        self.window = 1
        self.layout: LayoutKind | None = LayoutKind.LATIN
        self.is_console = False
        self.is_blocked_by_elevation = False
        self.release_in_time = True
        """What wait_for_release returns. False means the chord keys were held too long."""
        self.during_action: Callable[[], None] | None = None
        """Runs once, inside the next wait_for_release: events that arrive while an action runs."""
        self.clipboard_text: str | None = None
        self.selection: str | None = None
        """The text a copy puts on the clipboard; None when nothing is selected."""
        self.clipboard_locked: str | None = None
        """"save" or "set": that clipboard call raises ClipboardUnavailableError."""

    def wait_for_release(self, vks: Collection[int], timeout_ms: int) -> bool:
        during = self.during_action
        self.during_action = None
        if during is not None:
            during()
        return self.release_in_time

    def send_backspaces(self, count: int) -> None:
        self.calls.append(f"backspaces {count}")

    def type_text(self, text: str) -> None:
        self.calls.append(f"type {text}")

    def send_shortcut(self, shortcut: Shortcut) -> None:
        self.calls.append(f"shortcut {shortcut.value}")
        if shortcut is Shortcut.COPY and self.selection is not None:
            self.clipboard_text = self.selection
            self._clipboard_sequence += 1

    def save_clipboard(self) -> object:
        if self.clipboard_locked == "save":
            raise ClipboardUnavailableError("locked")
        return _SavedClipboard(self.clipboard_text)

    def restore_clipboard(self, saved: object) -> None:
        if not isinstance(saved, _SavedClipboard):
            raise TypeError(f"restore_clipboard takes what save_clipboard returned, not {type(saved).__name__}.")
        self.clipboard_text = saved.text
        self._clipboard_sequence += 1
        self.calls.append(f"restoreClipboard {'' if self.clipboard_text is None else self.clipboard_text}")

    def clipboard_sequence(self) -> int:
        return self._clipboard_sequence

    def read_clipboard_text(self) -> str | None:
        return self.clipboard_text

    def set_clipboard_text(self, text: str) -> None:
        if self.clipboard_locked == "set":
            raise ClipboardUnavailableError("locked")
        self.clipboard_text = text
        self._clipboard_sequence += 1
        self.calls.append(f"setClipboard {text}")

    def switch_layout(self, layout: LayoutKind) -> None:
        self.layout = layout
        self.calls.append(f"switchLayout {layout.value}")

    def foreground_info(self) -> ForegroundWindow:
        return ForegroundWindow(self.window, self.layout, self.is_console, self.is_blocked_by_elevation)

    def sleep(self, milliseconds: int) -> None:
        pass

    def notify(self, message: str) -> None:
        self.calls.append(f"notify {message}")


assert isinstance(FakePlatform(), Platform), "FakePlatform must satisfy the Platform protocol."
