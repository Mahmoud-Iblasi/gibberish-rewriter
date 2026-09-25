"""Builds the event arrays InputSender passes to SendInput. Pure, so it is unit-tested.

Mirrors ``csharp/src/GibberishRewriter.App/Win/InputBuilder.cs``.
"""

from __future__ import annotations

from collections.abc import Iterator

from gibberish_rewriter.core.platform import Shortcut

from gibberish_rewriter.win import win32
from gibberish_rewriter.win.win32 import INPUT, INPUT_KEYBOARD, KEYBDINPUT, InputUnion

EXTRA_INFO = 0x47525752
"""dwExtraInfo on every event this app sends ("GRWR"); KeyboardHook recognizes the app's own input by it."""

CHUNK_SIZE = 50
"""SendInput is called with at most this many events at a time."""

VK_BACK = 0x08
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_SPACE = 0x20
VK_INSERT = 0x2D
VK_C = 0x43
VK_V = 0x56
VK_Z = 0x5A
VK_LWIN = 0x5B


def key(vk: int, up: bool) -> INPUT:
    """One virtual-key event."""
    flags = (win32.KEYEVENTF_KEYUP if up else 0) | (
        win32.KEYEVENTF_EXTENDEDKEY if _is_extended(vk) else 0
    )
    return INPUT(
        type=INPUT_KEYBOARD,
        u=InputUnion(ki=KEYBDINPUT(wVk=vk, dwFlags=flags, dwExtraInfo=EXTRA_INFO)),
    )


def unicode(unit: int, up: bool) -> INPUT:
    """One KEYEVENTF_UNICODE event. C# takes a ``char``; ``unit`` is that UTF-16 code unit as a number, because
    Python's ``str`` iterates code points rather than code units."""
    flags = win32.KEYEVENTF_UNICODE | (win32.KEYEVENTF_KEYUP if up else 0)
    return INPUT(
        type=INPUT_KEYBOARD,
        u=InputUnion(ki=KEYBDINPUT(wScan=unit, dwFlags=flags, dwExtraInfo=EXTRA_INFO)),
    )


def key_press(vk: int) -> list[INPUT]:
    """One press (down, up) of a virtual key: the CapsLock replay or the 0xE8 mask key."""
    return [key(vk, False), key(vk, True)]


def backspaces(count: int) -> list[INPUT]:
    events: list[INPUT] = []
    for _ in range(count):
        events.append(key(VK_BACK, False))
        events.append(key(VK_BACK, True))
    return events


def text(value: str) -> list[INPUT]:
    """Each UTF-16 unit as a KEYEVENTF_UNICODE down and up.

    A character outside the basic plane is two units, exactly as it is two ``char`` values in C#.
    """
    units = value.encode("utf-16-le", "surrogatepass")
    events: list[INPUT] = []
    for index in range(0, len(units), 2):
        unit = units[index] | (units[index + 1] << 8)
        events.append(unicode(unit, False))
        events.append(unicode(unit, True))
    return events


def shortcut(which: Shortcut, console: bool) -> list[INPUT]:
    """Ctrl+C / Ctrl+V / Ctrl+Z, or Ctrl+Insert / Shift+Insert in console windows."""
    if which is Shortcut.COPY:
        modifier, trigger = (VK_CONTROL, VK_INSERT) if console else (VK_CONTROL, VK_C)
    elif which is Shortcut.PASTE:
        modifier, trigger = (VK_SHIFT, VK_INSERT) if console else (VK_CONTROL, VK_V)
    else:
        modifier, trigger = VK_CONTROL, VK_Z
    return [key(modifier, False), key(trigger, False), key(trigger, True), key(modifier, True)]


def win_space() -> list[INPUT]:
    """Win+Space, the layout-switch fallback."""
    return [key(VK_LWIN, False), key(VK_SPACE, False), key(VK_SPACE, True), key(VK_LWIN, True)]


def chunks(events: list[INPUT]) -> Iterator[list[INPUT]]:
    for start in range(0, len(events), CHUNK_SIZE):
        yield events[start : min(start + CHUNK_SIZE, len(events))]


def _is_extended(vk: int) -> bool:
    return vk in (VK_INSERT, VK_LWIN)
