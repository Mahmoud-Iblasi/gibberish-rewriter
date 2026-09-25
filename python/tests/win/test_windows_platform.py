"""win/windows_platform.py. The C# has no WindowsPlatformTests; most of the class forwards one call, but
wait_for_release and the console choice are real decisions the Core depends on, and both run headlessly with the
two Win32 calls stubbed."""

from __future__ import annotations

import time

import pytest
from gibberish_rewriter.core.platform import Platform, Shortcut

from gibberish_rewriter.win import foreground, win32, windows_platform
from gibberish_rewriter.win.key_state import KeyStateTracker
from gibberish_rewriter.win.windows_platform import WindowsPlatform

VK_SHIFT = 0x10
VK_CAPS_LOCK = 0x14


class FakeSender:
    """Records what InputSender was asked to send."""

    def __init__(self) -> None:
        self.shortcuts: list[tuple[Shortcut, bool]] = []

    def shortcut(self, shortcut: Shortcut, console: bool) -> None:
        self.shortcuts.append((shortcut, console))


def make(keys: KeyStateTracker | None = None) -> tuple[WindowsPlatform, FakeSender, list[str]]:
    sender = FakeSender()
    notified: list[str] = []
    platform = WindowsPlatform(
        pair=None,  # type: ignore[arg-type]
        sender=sender,  # type: ignore[arg-type]
        clipboard=None,  # type: ignore[arg-type]
        switcher=None,  # type: ignore[arg-type]
        keys=keys if keys is not None else KeyStateTracker(),
        notify=notified.append,
    )
    return platform, sender, notified


def test_windows_platform_is_the_cores_platform():
    """Plan decision 9: inherited, not duck-typed, so a wrong signature is an error at import."""
    assert issubclass(WindowsPlatform, Platform)
    platform, _sender, _notified = make()
    assert isinstance(platform, Platform)


@pytest.fixture
def no_key_down(monkeypatch):
    monkeypatch.setattr(win32, "GetAsyncKeyState", lambda vk: 0)


def test_wait_for_release_returns_at_once_when_nothing_is_down(no_key_down):
    platform, _sender, _notified = make()
    assert platform.wait_for_release([VK_SHIFT, VK_CAPS_LOCK], 3000) is True


def test_a_swallowed_key_is_seen_only_through_the_hooks_tracker(no_key_down):
    """Windows' key state never shows CapsLock or the trigger, because they were
    swallowed, so the tracker is the only place they are down."""
    keys = KeyStateTracker()
    platform, _sender, _notified = make(keys)
    assert platform.wait_for_release([VK_CAPS_LOCK], 0) is True
    keys.set(VK_CAPS_LOCK, True)
    assert platform.wait_for_release([VK_CAPS_LOCK], 0) is False


def test_wait_for_release_gives_up_after_the_timeout(no_key_down):
    keys = KeyStateTracker()
    keys.set(VK_CAPS_LOCK, True)
    platform, _sender, _notified = make(keys)

    started = time.monotonic()
    assert platform.wait_for_release([VK_CAPS_LOCK], 50) is False
    assert time.monotonic() - started >= 0.05


def test_wait_for_release_returns_once_windows_reports_the_key_up(monkeypatch):
    """A key Windows does see: GetAsyncKeyState is negative while it is held."""
    polls: list[int] = []

    def fake(vk: int) -> int:
        polls.append(vk)
        return -1 if len(polls) <= 3 else 0

    monkeypatch.setattr(win32, "GetAsyncKeyState", fake)
    platform, _sender, _notified = make()
    assert platform.wait_for_release([VK_SHIFT], 3000) is True
    assert len(polls) > 3


@pytest.mark.parametrize(
    ("class_name", "console"),
    [
        ("ConsoleWindowClass", True),
        ("CASCADIA_HOSTING_WINDOW_CLASS", True),
        ("Notepad", False),
        ("Chrome_WidgetWin_1", False),
    ],
)
def test_send_shortcut_asks_the_foreground_window_whether_it_is_a_console(
    monkeypatch, class_name, console
):
    """A console gets Ctrl+Insert and Shift+Insert instead of Ctrl+C and Ctrl+V."""
    monkeypatch.setattr(win32, "GetForegroundWindow", lambda: 1)
    monkeypatch.setattr(foreground, "class_name_of", lambda window: class_name)
    platform, sender, _notified = make()

    platform.send_shortcut(Shortcut.COPY)

    assert sender.shortcuts == [(Shortcut.COPY, console)]


def test_sleep_converts_milliseconds_to_seconds(monkeypatch):
    """The contract is the unit, not the clock: Windows' timer granularity makes a wall-clock assertion flaky."""
    platform, _sender, _notified = make()
    slept: list[float] = []
    monkeypatch.setattr(windows_platform.time, "sleep", slept.append)

    platform.sleep(40)

    assert slept == [0.04]


def test_notify_hands_the_message_to_the_host():
    platform, _sender, notified = make()
    platform.notify("Can't fix text in an administrator window.")
    assert notified == ["Can't fix text in an administrator window."]
