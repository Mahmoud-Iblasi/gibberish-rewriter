"""The pure part of the hooks: hook arguments in Engine's terms.

Mirrors ``csharp/src/GibberishRewriter.App/Win/HookTranslator.cs``. The C# static class becomes module functions,
so ``hook_translator.is_key_down(...)`` reads beside ``HookTranslator.IsKeyDown(...)``.
"""

from __future__ import annotations

from collections.abc import Callable

from gibberish_rewriter.core.key_names import HoldKeys

from gibberish_rewriter.win import win32
from gibberish_rewriter.win.input_builder import EXTRA_INFO

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_LWIN = 0x5B
VK_RWIN = 0x5C

_UINT_MAX = 0xFFFFFFFF

_DOWN_MESSAGES = (win32.WM_KEYDOWN, win32.WM_SYSKEYDOWN)

_MOUSE_DOWN_MESSAGES = (
    win32.WM_LBUTTONDOWN,
    win32.WM_RBUTTONDOWN,
    win32.WM_MBUTTONDOWN,
    win32.WM_XBUTTONDOWN,
)


def is_key_down(message: int) -> bool:
    """WM_KEYDOWN or WM_SYSKEYDOWN. The C# casts the ``IntPtr`` wParam to ``int`` first, which keeps its low 32
    bits, so the same masking is done here."""
    return (message & _UINT_MAX) in _DOWN_MESSAGES


def is_injected_by_self(flags: int, extra_info: int) -> bool:
    """True for input this app sent: injected, and carrying :data:`input_builder.EXTRA_INFO`."""
    return bool(flags & win32.LLKHF_INJECTED) and extra_info == EXTRA_INFO


def modifiers(is_down: Callable[[int], bool]) -> HoldKeys:
    """Shift, Ctrl, Alt and Win from a key-state query such as GetAsyncKeyState."""
    holds = HoldKeys.NONE
    if is_down(VK_SHIFT):
        holds |= HoldKeys.SHIFT
    if is_down(VK_CONTROL):
        holds |= HoldKeys.CTRL
    if is_down(VK_MENU):
        holds |= HoldKeys.ALT
    if is_down(VK_LWIN) or is_down(VK_RWIN):
        holds |= HoldKeys.WIN
    return holds


def is_mouse_button_down(message: int) -> bool:
    """A button press, not a move or a release."""
    return (message & _UINT_MAX) in _MOUSE_DOWN_MESSAGES
