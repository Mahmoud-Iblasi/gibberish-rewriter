"""Reinstalls the hooks when Windows has silently removed one.

Mirrors ``csharp/src/GibberishRewriter.App/Win/HookWatchdog.cs``. The C#'s two static members become module
functions, as in ``hkl.py``; the timer becomes a daemon thread waiting on an event, because Python has no
``System.Threading.Timer``.
"""

from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable

from gibberish_rewriter.win import win32
from gibberish_rewriter.win.win32 import LASTINPUTINFO

INTERVAL_MS = 5000
STALE_AFTER_MS = 2000

_UINT_MAX = 0xFFFFFFFF


class HookActivity:
    """The time of the hooks' last event, in the milliseconds hook structs and GetLastInputInfo use."""

    def __init__(self) -> None:
        self._last_event_time = 0

    @property
    def last_event_time(self) -> int:
        """The last time noted, as an unsigned 32-bit value. The C# reads an ``int`` field with ``Volatile.Read``
        and casts it back to ``uint``; here the masking is done on the way in and a plain attribute read is
        already atomic under the GIL."""
        return self._last_event_time

    def note(self, time: int) -> None:
        """The hook thread writes this; the watchdog thread reads it."""
        self._last_event_time = time & _UINT_MAX


def is_stale(last_input_time: int, last_hook_time: int, blocked_by_elevation: bool) -> bool:
    """True when Windows saw input more than :data:`STALE_AFTER_MS` after the hooks' last event.

    Tick counts wrap after 49.7 days, so the gap is taken modulo 2**32 and a "negative" gap is not stale.
    """
    gap = (last_input_time - last_hook_time) & _UINT_MAX
    return not blocked_by_elevation and gap > STALE_AFTER_MS and gap < 0x80000000


def missed_input_message(gap_ms: int, foreground_class: str) -> str:
    """Mirrors C#'s MissedInputMessage: the gap and the foreground window's class show where the missed input went."""
    return f"The hooks missed input for {gap_ms} ms (foreground: {foreground_class}); reinstalling them"


def last_input_time() -> int | None:
    """GetLastInputInfo's time, or None if the call fails."""
    info = LASTINPUTINFO(cbSize=ctypes.sizeof(LASTINPUTINFO))
    return info.dwTime if win32.GetLastInputInfo(ctypes.byref(info)) else None


class HookWatchdog:
    """Checks every :data:`INTERVAL_MS` and reinstalls the hooks when they have gone quiet while Windows has not."""

    def __init__(
        self,
        activity: HookActivity,
        foreground_blocked_by_elevation: Callable[[], bool],
        reinstall: Callable[[], None],
        log: Callable[[str], None],
        foreground_class: Callable[[], str] = lambda: "unknown",
    ) -> None:
        """Starts checking straight away, as the C# constructor starts its timer."""
        self._activity = activity
        self._foreground_blocked_by_elevation = foreground_blocked_by_elevation
        self._reinstall = reinstall
        self._log = log
        self._foreground_class = foreground_class
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="HookWatchdog", daemon=True)
        self._thread.start()

    def close(self) -> None:
        """The C#'s Dispose: stops the checks and waits for the thread."""
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(2.0)

    def __enter__(self) -> HookWatchdog:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _run(self) -> None:
        # wait() returns True only when close() set the event, so a plain timeout runs the next check.
        while not self._stop.wait(INTERVAL_MS / 1000):
            self._check()

    def _check(self) -> None:
        try:
            last_input = last_input_time()
            if last_input is None or not is_stale(
                last_input, self._activity.last_event_time, self._foreground_blocked_by_elevation()
            ):
                return
            gap = (last_input - self._activity.last_event_time) & 0xFFFF_FFFF
            self._log(missed_input_message(gap, self._foreground_class()))
            self._activity.note(last_input)
            self._reinstall()
        except Exception as exception:  # noqa: BLE001 - the watchdog thread must outlive any one bad check
            self._log(f"Hook watchdog error: {type(exception).__name__}")
