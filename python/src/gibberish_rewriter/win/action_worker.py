"""One worker thread runs actions in order, each exactly once.

Mirrors ``csharp/src/GibberishRewriter.App/Win/ActionWorker.cs``.
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable

from gibberish_rewriter.core.chord_detector import ChordAction
from gibberish_rewriter.core.engine import Engine

from gibberish_rewriter.win import win32

JOIN_TIMEOUT_MS = 2000
"""How long close() waits for the queue to drain, as the C# waits on Thread.Join(2000)."""

_VK_CAPITAL = 0x14

_STOP = None
"""The sentinel that ends the loop, standing in for BlockingCollection.CompleteAdding()."""


class ActionWorker:
    """One background thread running queued actions in order."""

    def __init__(self, log: Callable[[str], None]) -> None:
        self._log = log
        self._queue: queue.Queue[tuple[Engine, ChordAction] | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="Actions", daemon=True)
        self._thread.start()

    def enqueue(self, engine: Engine, action: ChordAction) -> None:
        """Hook thread, from Engine's start_action. Only queues, so the hook returns at once."""
        self._queue.put((engine, action))

    def close(self) -> None:
        self._queue.put(_STOP)
        self._thread.join(JOIN_TIMEOUT_MS / 1000)

    def __enter__(self) -> ActionWorker:
        return self

    def __exit__(self, *exception: object) -> None:
        self.close()

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is _STOP:
                return
            engine, action = item
            try:
                engine.run_action(action)
                self._log(f"Ran {action.value}")
            except Exception as exception:  # noqa: BLE001 - an action must never end the worker thread
                self._log(f"{action.value} failed: {type(exception).__name__}")


def caps_lock_is_on() -> bool:
    """The Caps Lock toggle as Windows reports it, for Engine's caps_lock_on.

    C# has this as the static class ``CapsLockState``; ``hkl.py`` sets the precedent of a module function.
    """
    return win32.GetKeyState(_VK_CAPITAL) & 1 != 0
