"""win/action_worker.py. The C# has no ActionWorkerTests, but the host's threading rules are exactly
what this class promises -- one thread, in order, each action exactly once -- and none of it needs a desktop."""

from __future__ import annotations

import threading

from gibberish_rewriter.core.chord_detector import ChordAction

from gibberish_rewriter.win import action_worker
from gibberish_rewriter.win.action_worker import ActionWorker


class FakeEngine:
    """Records the actions it was asked to run and on which thread. Duck-typed, like the hooks' Engine."""

    def __init__(self, fail_on: ChordAction | None = None) -> None:
        self.ran: list[ChordAction] = []
        self.threads: set[int] = set()
        self._fail_on = fail_on

    def run_action(self, action: ChordAction) -> None:
        self.threads.add(threading.get_ident())
        self.ran.append(action)
        if action is self._fail_on:
            raise RuntimeError("the action failed")


def test_actions_run_in_order_on_one_thread_that_is_not_the_caller():
    engine = FakeEngine()
    lines: list[str] = []
    worker = ActionWorker(lines.append)
    for _ in range(5):
        worker.enqueue(engine, ChordAction.FIX_TYPED)
        worker.enqueue(engine, ChordAction.FIX_SELECTION)
    worker.close()

    assert engine.ran == [ChordAction.FIX_TYPED, ChordAction.FIX_SELECTION] * 5
    assert len(engine.threads) == 1
    assert threading.get_ident() not in engine.threads
    assert lines == ["Ran fix_typed", "Ran fix_selection"] * 5


def test_close_runs_what_is_already_queued():
    """C# calls CompleteAdding, which lets the consumer drain the queue before it stops."""
    engine = FakeEngine()
    worker = ActionWorker(lambda _line: None)
    for _ in range(20):
        worker.enqueue(engine, ChordAction.FIX_TYPED)
    worker.close()

    assert len(engine.ran) == 20


def test_an_action_that_raises_is_logged_and_the_worker_keeps_going():
    engine = FakeEngine(fail_on=ChordAction.FIX_SELECTION)
    lines: list[str] = []
    worker = ActionWorker(lines.append)
    worker.enqueue(engine, ChordAction.FIX_SELECTION)
    worker.enqueue(engine, ChordAction.FIX_TYPED)
    worker.close()

    assert engine.ran == [ChordAction.FIX_SELECTION, ChordAction.FIX_TYPED]
    assert lines == ["fix_selection failed: RuntimeError", "Ran fix_typed"]


def test_nothing_typed_reaches_the_log():
    """The log records event kinds only."""
    engine = FakeEngine()
    lines: list[str] = []
    worker = ActionWorker(lines.append)
    worker.enqueue(engine, ChordAction.FIX_TYPED)
    worker.close()

    assert lines == ["Ran fix_typed"]


def test_caps_lock_is_on_reports_the_toggle_as_a_bool():
    """Engine takes the toggle Windows reports, not the key's up or down state."""
    assert caps_lock_state() in (True, False)
    assert isinstance(caps_lock_state(), bool)


def caps_lock_state() -> bool:
    return action_worker.caps_lock_is_on()
