"""One thread installs both hooks and runs a message loop and nothing else, so a busy UI never delays a
hook past Windows' 1 s limit, after which Windows silently removes it.

Mirrors ``csharp/src/GibberishRewriter.App/Win/HookThread.cs``.
"""

from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable

from gibberish_rewriter.win import hook_watchdog, win32
from gibberish_rewriter.win.hook_watchdog import HookActivity
from gibberish_rewriter.win.keyboard_hook import KeyboardHook
from gibberish_rewriter.win.mouse_hook import MouseHook
from gibberish_rewriter.win.win32 import MSG

WM_REINSTALL = win32.WM_APP + 1
"""The private message :meth:`HookThread.reinstall` posts to the hook thread."""

JOIN_TIMEOUT_MS = 2000


class HookThread:
    """Installs both hooks on its own thread and keeps a GetMessageW loop running there."""

    def __init__(
        self,
        keyboard: KeyboardHook,
        mouse: MouseHook,
        activity: HookActivity,
        reinstalled: Callable[[], None],
        log: Callable[[str], None],
    ) -> None:
        """``reinstalled`` runs on the hook thread after a reinstall. Keep it quick."""
        self._keyboard = keyboard
        self._mouse = mouse
        self._activity = activity
        self._reinstalled = reinstalled
        self._log = log
        self._ready = threading.Event()
        self._thread_id = 0
        # The C# also raises the thread's priority to AboveNormal; Python's threading has no equivalent.
        self._thread = threading.Thread(target=self._run, name="Hooks", daemon=True)

    @property
    def thread_id(self) -> int:
        """The hook thread's Windows thread id, or 0 before :meth:`start`."""
        return self._thread_id

    def start(self) -> None:
        """Starts the thread and returns once both hooks are installed."""
        self._thread.start()
        self._ready.wait()

    def reinstall(self) -> None:
        """Any thread. Reinstalls both hooks on the hook thread."""
        win32.PostThreadMessage(self._thread_id, WM_REINSTALL, 0, 0)

    def close(self) -> None:
        """The C#'s Dispose: asks the loop to end and waits for the thread."""
        if self._thread.is_alive():
            win32.PostThreadMessage(self._thread_id, win32.WM_QUIT, 0, 0)
            self._thread.join(JOIN_TIMEOUT_MS / 1000)

    def __enter__(self) -> HookThread:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _run(self) -> None:
        self._thread_id = win32.GetCurrentThreadId()
        message = MSG()
        # Creates the thread's message queue, so PostThreadMessage works from the first moment.
        win32.PeekMessage(ctypes.byref(message), None, win32.WM_USER, win32.WM_USER, win32.PM_NOREMOVE)
        self._install()
        self._ready.set()

        while win32.GetMessage(ctypes.byref(message), None, 0, 0) > 0:
            if message.message != WM_REINSTALL:
                continue
            try:
                self._uninstall()
                self._install()
                self._reinstalled()
            except Exception as exception:  # noqa: BLE001 - an exception escaping the hook thread ends the app
                self._log(f"Hook reinstall error: {type(exception).__name__}")
        self._uninstall()

    def _install(self) -> None:
        self._activity.note(hook_watchdog.last_input_time() or 0)
        self._keyboard.install()
        self._mouse.install()

    def _uninstall(self) -> None:
        self._keyboard.uninstall()
        self._mouse.uninstall()
