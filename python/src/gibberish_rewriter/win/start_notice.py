"""The start notification waits until Windows can show it.

Mirrors ``csharp/src/GibberishRewriter.App/Win/StartNotice.cs``. Started at sign-in, the app can come up before the
taskbar exists or while Windows holds notifications back, and a balloon shown then is lost.
"""

from __future__ import annotations

import ctypes

from gibberish_rewriter.win import win32

POLL_INTERVAL_MS = 500
MAX_WAIT_MS = 60_000


def should_show(taskbar_exists: bool, notification_state: int, waited_ms: int) -> bool:
    """True once the taskbar exists and Windows accepts notifications, or after MAX_WAIT_MS, so a Windows that never
    reports ready still gets the attempt."""
    return waited_ms >= MAX_WAIT_MS or (
        taskbar_exists and notification_state == win32.QUNS_ACCEPTS_NOTIFICATIONS
    )


def taskbar_exists() -> bool:
    return bool(win32.FindWindow("Shell_TrayWnd", None))


def notification_state() -> int:
    """SHQueryUserNotificationState's QUNS value, or 0 if the call fails."""
    state = ctypes.c_int()
    return state.value if win32.SHQueryUserNotificationState(ctypes.byref(state)) == 0 else 0
