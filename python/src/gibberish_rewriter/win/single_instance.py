"""The named mutex both apps take.

Mirrors ``csharp/src/GibberishRewriter.App/Win/SingleInstance.cs``. C# has ``System.Threading.Mutex``; here the
three kernel32 entry points are bound in this module, next to the only code that uses them.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from gibberish_rewriter.win import win32

MUTEX_NAME = r"Local\GibberishRewriter.SingleInstance"

_ERROR_ALREADY_EXISTS = 183

_CreateMutex = win32.kernel32.CreateMutexW
_CreateMutex.restype = wintypes.HANDLE
_CreateMutex.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]

_ReleaseMutex = win32.kernel32.ReleaseMutex
_ReleaseMutex.restype = wintypes.BOOL
_ReleaseMutex.argtypes = [wintypes.HANDLE]


class InstanceLock:
    """The held mutex. Keep it until the app exits; closing it lets the next copy start."""

    def __init__(self, handle: int) -> None:
        self._handle: int | None = handle

    def close(self) -> None:
        handle, self._handle = self._handle, None
        if handle is not None:
            _ReleaseMutex(handle)
            win32.CloseHandle(handle)

    def __enter__(self) -> InstanceLock:
        return self

    def __exit__(self, *exception: object) -> None:
        self.close()


def try_acquire(name: str = MUTEX_NAME) -> InstanceLock | None:
    """The mutex, held; or None when another copy (C# or Python) holds it.

    ``CreateMutexW`` with ``bInitialOwner`` returns the existing handle and sets ERROR_ALREADY_EXISTS when the
    mutex was already there, which is what C#'s ``createdNew`` flag reports.
    """
    handle = _CreateMutex(None, True, name)
    if not handle:
        return None
    if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
        win32.CloseHandle(handle)
        return None
    return InstanceLock(handle)
