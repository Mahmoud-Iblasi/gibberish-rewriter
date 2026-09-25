"""Installed layouts, and the key table read from Windows.

Mirrors ``csharp/src/GibberishRewriter.App/Win/LayoutReader.cs``. The C# static class becomes module functions.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from gibberish_rewriter.core.key_names import KeyNames
from gibberish_rewriter.core.key_table import KeyEntry, KeyState, KeyTable

from gibberish_rewriter.win import hkl, win32
from gibberish_rewriter.win.hkl import LayoutPair

VK_SHIFT = 0x10
VK_LSHIFT = 0xA0
VK_CAPITAL = 0x14
VK_NUMLOCK = 0x90
VK_KEY_A = 0x41

DONT_CHANGE_KEYBOARD_STATE = 4
"""ToUnicodeEx's ``wFlags`` bit 2: read the layout without touching the real keyboard state."""

TEXT_BUFFER_LENGTH = 16
"""The C# passes a ``char[16]``; ``cchBuff`` is the count of UTF-16 units, not bytes."""

_STATES = (KeyState.PLAIN, KeyState.SHIFT, KeyState.CAPS, KeyState.SHIFT_CAPS)


class DeadKeyError(Exception):
    """A layout has a dead key, which Gibberish Rewriter doesn't support."""

    def __init__(self, layout: int, key: str) -> None:
        super().__init__(f"Layout {hkl.format(layout)} has a dead key: {key}.")
        self.layout = layout


def installed_layouts() -> tuple[int, ...]:
    """Installed layouts as low 32-bit HKL values, in GetKeyboardLayoutList order."""
    size = win32.GetKeyboardLayoutList(0, None)
    handles = (wintypes.HKL * size)()
    count = win32.GetKeyboardLayoutList(size, handles)
    # The C# indexes an array of the first call's size and takes the second call's count; clamping keeps a count
    # that somehow grew between the two calls from running off the end of the array.
    return tuple(hkl.low32(handles[index] or 0) for index in range(min(count, size)))


def installed_with_key_a() -> tuple[tuple[int, str], ...]:
    """Each installed layout with what its KeyA types plain ("" if KeyA is a dead key), for "auto"."""
    return tuple((layout, _key_a_text(layout)) for layout in installed_layouts())


def read_table(names: KeyNames, pair: LayoutPair) -> KeyTable:
    """The key table for the pair, keys in keys.json ``tableKeys`` order. Raises :class:`DeadKeyError`."""
    entries: list[KeyEntry] = []
    for key in names.table_keys:
        vk = names.trigger_vk(key)
        if vk is None:
            raise ValueError(f"tableKeys lists unknown key {key}.")
        entries.append(KeyEntry(key, vk, _read_key(pair.latin, key, vk), _read_key(pair.arabic, key, vk)))
    return KeyTable(hkl.format(pair.latin), hkl.format(pair.arabic), entries)


def _key_a_text(layout: int) -> str:
    try:
        return read_text(layout, "KeyA", VK_KEY_A, KeyState.PLAIN)
    except DeadKeyError:
        return ""


def _read_key(layout: int, key: str, vk: int) -> tuple[str, ...]:
    return tuple(read_text(layout, key, vk, state) for state in _STATES)


def read_text(layout: int, key: str, vk: int, state: KeyState) -> str:
    """What one key types on one layout in one modifier state. Raises :class:`DeadKeyError` for a dead key."""
    handle = hkl.to_handle(layout)
    key_state = win32.key_state_buffer()
    key_state[VK_NUMLOCK] = 0x01
    if state in (KeyState.SHIFT, KeyState.SHIFT_CAPS):
        key_state[VK_SHIFT] = 0x80
        key_state[VK_LSHIFT] = 0x80
    if state in (KeyState.CAPS, KeyState.SHIFT_CAPS):
        key_state[VK_CAPITAL] = 0x01
    # Only the low byte: an 0xE0 prefix sets the high bit, which ToUnicodeEx reads as a key release.
    scan = win32.MapVirtualKeyEx(vk, win32.MAPVK_VK_TO_VSC_EX, handle) & 0xFF
    buffer = ctypes.create_unicode_buffer(TEXT_BUFFER_LENGTH)
    length = win32.ToUnicodeEx(
        vk, scan, key_state, buffer, TEXT_BUFFER_LENGTH, DONT_CHANGE_KEYBOARD_STATE, handle
    )
    if length < 0:
        raise DeadKeyError(layout, key)
    return buffer[:length]
