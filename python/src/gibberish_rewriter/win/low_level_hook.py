"""A WH_KEYBOARD_LL or WH_MOUSE_LL hook. ``install`` and ``uninstall`` run on the hook thread.

Mirrors ``csharp/src/GibberishRewriter.App/Win/LowLevelHook.cs``.
"""

from __future__ import annotations

import abc
import ctypes
from collections.abc import Callable

from gibberish_rewriter.win import win32


class LowLevelHook(abc.ABC):
    """A WH_KEYBOARD_LL or WH_MOUSE_LL hook."""

    def __init__(self, kind: int, log: Callable[[str], None]) -> None:
        self._kind = kind
        # Kept in a field for the hook's lifetime, so the callback Windows calls is never garbage-collected.
        # ctypes frees the trampoline together with this object, and Windows then stops calling the
        # hook without saying so: no error, no event, nothing to see but a keyboard that no longer answers.
        self._callback = win32.LowLevelHookProc(self._dispatch)
        self._handle = 0
        self._log = log

    @property
    def handle(self) -> int:
        """The hook handle, or 0 when it is not installed."""
        return self._handle

    def install(self) -> None:
        self._handle = (
            win32.SetWindowsHookEx(self._kind, self._callback, win32.GetModuleHandle(None), 0) or 0
        )
        if self._handle == 0:
            self._log(f"{type(self).__name__} install failed (error {ctypes.get_last_error()})")

    def uninstall(self) -> None:
        if self._handle != 0:
            win32.UnhookWindowsHookEx(self._handle)
            self._handle = 0

    @abc.abstractmethod
    def on_event(self, message: int, data: int) -> bool:
        """True to swallow the event. ``data`` is the address of the hook structure."""

    def _dispatch(self, code: int, message: int, data: int) -> int:
        if code == win32.HC_ACTION:
            try:
                if self.on_event(message, data):
                    return 1
            except Exception as exception:  # noqa: BLE001 - an exception escaping a hook callback ends the process
                self._log(f"{type(self).__name__} error: {type(exception).__name__}")
        return win32.CallNextHookEx(self._handle, code, message, data)
