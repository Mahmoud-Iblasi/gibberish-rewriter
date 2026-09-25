"""The foreground window, its layout, whether it is a console, and elevation.

Mirrors ``csharp/src/GibberishRewriter.App/Win/Foreground.cs``. The C# static class becomes module functions.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from gibberish_rewriter.core.platform import ForegroundWindow

from gibberish_rewriter.win import win32
from gibberish_rewriter.win.hkl import LayoutPair

ERROR_ACCESS_DENIED = 5

CLASS_NAME_LENGTH = 256
"""The C# reads into a ``char[256]`` and passes its length, so at most 255 characters come back."""

CONSOLE_CLASSES = ("ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS")
"""The classic console and Windows Terminal."""


def is_console_class(class_name: str) -> bool:
    """Case-sensitive, as the C# ``is "ConsoleWindowClass" or ...`` pattern is."""
    return class_name in CONSOLE_CLASSES


def read(pair: LayoutPair) -> ForegroundWindow:
    """Everything Engine asks about the foreground window."""
    window = win32.GetForegroundWindow() or 0
    return ForegroundWindow(
        window,
        pair.kind_of(layout_of(window)),
        is_console_class(class_name_of(window)),
        is_blocked_by_elevation(window),
    )


def layout_of(window: int) -> int:
    """The layout handle of the thread that owns the window, sign-extended as Windows returns it."""
    process_id = wintypes.DWORD()
    thread_id = win32.GetWindowThreadProcessId(window, ctypes.byref(process_id))
    return win32.GetKeyboardLayout(thread_id) or 0


def class_name_of(window: int) -> str:
    """The window class, or the empty string when GetClassName fails (it returns 0, which the C# floors)."""
    buffer = ctypes.create_unicode_buffer(CLASS_NAME_LENGTH)
    length = win32.GetClassName(window, buffer, CLASS_NAME_LENGTH)
    return buffer[: max(length, 0)]


def is_blocked_by_elevation(window: int) -> bool:
    """True when the window's process runs as administrator and this app does not. Access denied counts as
    elevated."""
    if window == 0 or is_privileged_process():
        return False
    process_id = wintypes.DWORD()
    win32.GetWindowThreadProcessId(window, ctypes.byref(process_id))
    return _is_process_elevated(process_id.value)


def is_privileged_process() -> bool:
    """C#'s ``Environment.IsPrivilegedProcess``: on Windows, whether this process's token is elevated.

    .NET reads ``TokenElevation`` of the current process; the same question is asked here through this module's
    own process id, because ``win32.py`` binds ``OpenProcess`` but not ``GetCurrentProcess``.
    """
    return _is_process_elevated(os.getpid())


def _is_process_elevated(process_id: int) -> bool:
    process = win32.OpenProcess(win32.PROCESS_QUERY_LIMITED_INFORMATION, False, process_id)
    if not process:
        return ctypes.get_last_error() == ERROR_ACCESS_DENIED
    try:
        token = wintypes.HANDLE()
        if not win32.OpenProcessToken(process, win32.TOKEN_QUERY, ctypes.byref(token)):
            return ctypes.get_last_error() == ERROR_ACCESS_DENIED
        try:
            elevation = wintypes.DWORD()
            returned = wintypes.DWORD()
            ok = win32.GetTokenInformation(
                token,
                win32.TokenElevation,
                ctypes.byref(elevation),
                ctypes.sizeof(elevation),
                ctypes.byref(returned),
            )
            return bool(ok) and elevation.value != 0
        finally:
            win32.CloseHandle(token)
    finally:
        win32.CloseHandle(process)
