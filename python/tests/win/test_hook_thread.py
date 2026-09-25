"""win/hook_thread.py. The C# has no HookThreadTests. The message loop is the part of the threading model that has to work
before anything else does, and it can be tested for real without hooking the keyboard: the two hooks are fakes,
so the thread, its message queue, PostThreadMessage and WM_QUIT are exercised and nothing is installed."""

from __future__ import annotations

import threading

import pytest

from gibberish_rewriter.win import hook_thread, win32
from gibberish_rewriter.win.hook_thread import WM_REINSTALL, HookThread
from gibberish_rewriter.win.hook_watchdog import HookActivity

TIMEOUT = 5.0
"""Seconds to wait for the hook thread. Long enough for a loaded machine, short enough to fail rather than hang."""


class FakeHook:
    """Counts installs and uninstalls and remembers which thread made them."""

    def __init__(self) -> None:
        self.installs = 0
        self.uninstalls = 0
        self.threads: list[int] = []

    def install(self) -> None:
        self.installs += 1
        self.threads.append(threading.get_native_id())

    def uninstall(self) -> None:
        self.uninstalls += 1


class Harness:
    """A HookThread with fake hooks, plus an event the reinstall callback sets."""

    def __init__(self, on_reinstalled=None) -> None:
        self.keyboard = FakeHook()
        self.mouse = FakeHook()
        self.activity = HookActivity()
        self.lines: list[str] = []
        self.reinstalled = threading.Event()
        self._on_reinstalled = on_reinstalled
        self.thread = HookThread(
            self.keyboard, self.mouse, self.activity, self._note, self.lines.append
        )

    def _note(self) -> None:
        try:
            if self._on_reinstalled is not None:
                self._on_reinstalled()
        finally:
            self.reinstalled.set()

    def wait_for_reinstall(self) -> None:
        assert self.reinstalled.wait(TIMEOUT), "the hook thread never handled the reinstall message"
        self.reinstalled.clear()


@pytest.fixture
def harness():
    made: list[Harness] = []

    def build(on_reinstalled=None) -> Harness:
        harness = Harness(on_reinstalled)
        made.append(harness)
        return harness

    yield build
    for harness in made:
        harness.thread.close()


def test_start_returns_only_once_both_hooks_are_installed(harness):
    hooks = harness()
    assert hooks.keyboard.installs == 0
    hooks.thread.start()
    assert hooks.keyboard.installs == 1
    assert hooks.mouse.installs == 1


def test_the_hooks_are_installed_on_the_hook_thread_and_not_the_caller(harness):
    """A hook belongs to the thread that installed it, so this must never be the caller's thread."""
    hooks = harness()
    hooks.thread.start()
    assert hooks.keyboard.threads == hooks.mouse.threads
    assert hooks.keyboard.threads[0] != threading.get_native_id()
    assert hooks.thread.thread_id == hooks.keyboard.threads[0]


def test_installing_notes_the_time_so_the_watchdog_does_not_fire_at_once(harness):
    hooks = harness()
    hooks.thread.start()
    assert hooks.activity.last_event_time > 0


def test_reinstall_takes_both_hooks_down_and_puts_them_back(harness):
    hooks = harness()
    hooks.thread.start()
    hooks.thread.reinstall()
    hooks.wait_for_reinstall()
    assert (hooks.keyboard.uninstalls, hooks.keyboard.installs) == (1, 2)
    assert (hooks.mouse.uninstalls, hooks.mouse.installs) == (1, 2)
    assert hooks.lines == []


def test_reinstall_stays_on_the_hook_thread(harness):
    hooks = harness()
    hooks.thread.start()
    hooks.thread.reinstall()
    hooks.wait_for_reinstall()
    assert set(hooks.keyboard.threads) == {hooks.thread.thread_id}


def test_another_message_is_ignored(harness):
    """The loop reads every message the thread is sent; only WM_APP + 1 means reinstall."""
    hooks = harness()
    hooks.thread.start()
    win32.PostThreadMessage(hooks.thread.thread_id, win32.WM_USER, 0, 0)
    win32.PostThreadMessage(hooks.thread.thread_id, WM_REINSTALL, 0, 0)
    hooks.wait_for_reinstall()
    assert hooks.keyboard.installs == 2, "the WM_USER must not have reinstalled anything"


def test_an_error_after_a_reinstall_is_logged_and_the_loop_lives_on(harness):
    """An exception escaping the hook thread would end the app."""

    def boom() -> None:
        raise RuntimeError("tray gone")

    hooks = harness(boom)
    hooks.thread.start()
    hooks.thread.reinstall()
    hooks.wait_for_reinstall()
    assert hooks.lines == ["Hook reinstall error: RuntimeError"]

    hooks.thread.reinstall()
    hooks.wait_for_reinstall()
    assert hooks.keyboard.installs == 3, "the thread kept reading messages after the error"


def test_close_ends_the_loop_and_uninstalls_both_hooks(harness):
    hooks = harness()
    hooks.thread.start()
    hooks.thread.close()
    assert not hooks.thread._thread.is_alive()
    assert hooks.keyboard.uninstalls == 1
    assert hooks.mouse.uninstalls == 1


def test_close_before_start_does_nothing(harness):
    hooks = harness()
    hooks.thread.close()
    assert hooks.keyboard.installs == 0
    assert hooks.keyboard.uninstalls == 0


def test_close_twice_is_harmless(harness):
    hooks = harness()
    hooks.thread.start()
    hooks.thread.close()
    hooks.thread.close()
    assert hooks.keyboard.uninstalls == 1


def test_the_hook_thread_is_a_daemon_so_it_never_holds_the_app_open(harness):
    hooks = harness()
    assert hooks.thread._thread.daemon
    assert hooks.thread._thread.name == "Hooks"


def test_the_reinstall_message_is_private_to_this_app():
    assert WM_REINSTALL == win32.WM_APP + 1


def test_the_thread_can_be_used_as_a_context_manager():
    keyboard, mouse = FakeHook(), FakeHook()
    with HookThread(keyboard, mouse, HookActivity(), lambda: None, lambda _: None) as thread:
        thread.start()
        assert thread._thread.is_alive()
    assert not thread._thread.is_alive()
    assert keyboard.uninstalls == 1


def test_last_input_time_failing_still_installs(monkeypatch, harness):
    monkeypatch.setattr(hook_thread.hook_watchdog, "last_input_time", lambda: None)
    hooks = harness()
    hooks.thread.start()
    assert hooks.activity.last_event_time == 0
    assert hooks.keyboard.installs == 1
