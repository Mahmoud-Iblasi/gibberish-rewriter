"""A message-only window on the UI thread that owns the app's clipboard writes.

The UI thread's message loop answers the messages other apps' clipboard calls send the owner, so it never blocks
them. ``EmptyClipboard`` makes the window passed to ``OpenClipboard`` the clipboard owner, and an owner of NULL
makes ``SetClipboardData`` fail, so the app needs a real window even though nothing is ever drawn in it.

Mirrors ``csharp/src/GibberishRewriter.App/Win/ClipboardOwnerWindow.cs``, which is a WinForms ``NativeWindow``.
It also carries the session notification: the C# AppHost uses ``SystemEvents.SessionSwitch``, which is .NET's own
hidden window, and this is the app's hidden window.

The window entry points are bound here rather than in ``win32.py``, next to the only code that uses them.
"""

from __future__ import annotations

import ctypes
from collections.abc import Callable
from ctypes import wintypes

from gibberish_rewriter.win import win32

CLASS_NAME = "GibberishRewriter.ClipboardOwner"
WINDOW_NAME = "GibberishRewriter.ClipboardOwner"

_HWND_MESSAGE = -3
"""The parent that makes a window message-only: no screen space, no broadcasts, only sent messages."""

_WM_WTSSESSION_CHANGE = 0x02B1
_WTS_SESSION_UNLOCK = 0x8
_NOTIFY_FOR_THIS_SESSION = 0

_WNDPROC = ctypes.WINFUNCTYPE(
    win32.LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", _WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


_RegisterClass = win32.user32.RegisterClassW
_RegisterClass.restype = wintypes.ATOM
_RegisterClass.argtypes = [ctypes.POINTER(WNDCLASSW)]

_CreateWindowEx = win32.user32.CreateWindowExW
_CreateWindowEx.restype = wintypes.HWND
_CreateWindowEx.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    wintypes.LPVOID,
]

_DestroyWindow = win32.user32.DestroyWindow
_DestroyWindow.restype = wintypes.BOOL
_DestroyWindow.argtypes = [wintypes.HWND]

_DefWindowProc = win32.user32.DefWindowProcW
_DefWindowProc.restype = win32.LRESULT
_DefWindowProc.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

_wtsapi32 = ctypes.WinDLL("wtsapi32", use_last_error=True)

_WTSRegisterSessionNotification = _wtsapi32.WTSRegisterSessionNotification
_WTSRegisterSessionNotification.restype = wintypes.BOOL
_WTSRegisterSessionNotification.argtypes = [wintypes.HWND, wintypes.DWORD]

_WTSUnRegisterSessionNotification = _wtsapi32.WTSUnRegisterSessionNotification
_WTSUnRegisterSessionNotification.restype = wintypes.BOOL
_WTSUnRegisterSessionNotification.argtypes = [wintypes.HWND]

_WINDOWS: dict[int, ClipboardOwnerWindow] = {}
"""Handle to window, so the one shared window procedure can find whose callback to run."""


def _window_proc(handle: int, message: int, wparam: int, lparam: int) -> int:
    if message == _WM_WTSSESSION_CHANGE and wparam == _WTS_SESSION_UNLOCK:
        window = _WINDOWS.get(int(handle or 0))
        if window is not None and window.on_session_unlock is not None:
            try:
                window.on_session_unlock()
            except Exception:  # noqa: BLE001 - an exception here would cross back into Windows
                pass
    return _DefWindowProc(handle, message, wparam, lparam)


_WINDOW_PROC = _WNDPROC(_window_proc)
"""Kept for the process's lifetime: a collected ctypes callback takes the window with it (plan decision 4)."""

_atom = 0


def _register_class() -> int:
    """Registers the window class once. Windows keeps it until the process exits."""
    global _atom
    if _atom == 0:
        wndclass = WNDCLASSW()
        wndclass.lpfnWndProc = _WINDOW_PROC
        wndclass.hInstance = win32.GetModuleHandle(None)
        wndclass.lpszClassName = CLASS_NAME
        _atom = _RegisterClass(ctypes.byref(wndclass))
        if _atom == 0:
            raise OSError(ctypes.get_last_error(), "RegisterClassW failed for the clipboard owner window.")
    return _atom


class ClipboardOwnerWindow:
    """The app's message-only window. Create it on the thread that runs the message loop."""

    def __init__(self, on_session_unlock: Callable[[], None] | None = None) -> None:
        self.on_session_unlock = on_session_unlock
        _register_class()
        handle = _CreateWindowEx(
            0, CLASS_NAME, WINDOW_NAME, 0, 0, 0, 0, 0, wintypes.HWND(_HWND_MESSAGE), None, None, None
        )
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateWindowExW failed for the clipboard owner window.")
        self._handle: int | None = int(handle)
        _WINDOWS[self._handle] = self
        if on_session_unlock is not None:
            _WTSRegisterSessionNotification(handle, _NOTIFY_FOR_THIS_SESSION)

    @property
    def handle(self) -> int:
        """The HWND, passed to OpenClipboard from the action thread. 0 once the window is gone."""
        return self._handle or 0

    def close(self) -> None:
        handle, self._handle = self._handle, None
        if handle is None:
            return
        _WINDOWS.pop(handle, None)
        if self.on_session_unlock is not None:
            _WTSUnRegisterSessionNotification(wintypes.HWND(handle))
        _DestroyWindow(wintypes.HWND(handle))

    def __enter__(self) -> ClipboardOwnerWindow:
        return self

    def __exit__(self, *exception: object) -> None:
        self.close()
