"""win/low_level_hook.py. The C# has no LowLevelHookTests; its callback is the one place an exception would end
the process and the one place a garbage-collected delegate would silently kill the hooks, so both are
tested here against a stubbed SetWindowsHookEx and CallNextHookEx. No real hook is ever installed: this machine's
keyboard belongs to the user."""

from __future__ import annotations

import gc
import weakref

import pytest

from gibberish_rewriter.win import win32
from gibberish_rewriter.win.low_level_hook import LowLevelHook

NEXT_HOOK_RESULT = 0x2A
"""What the stubbed CallNextHookEx returns, so a passed-through event is unmistakable."""


class Recorder(LowLevelHook):
    """A hook that records what it was asked about and answers however the test set it up to."""

    def __init__(self, log, swallow=False, error=None):
        super().__init__(win32.WH_KEYBOARD_LL, log)
        self.events: list[tuple[int, int]] = []
        self.swallow = swallow
        self.error = error

    def on_event(self, message: int, data: int) -> bool:
        self.events.append((message, data))
        if self.error is not None:
            raise self.error
        return self.swallow


@pytest.fixture
def next_hook(monkeypatch):
    """Replaces CallNextHookEx and records every call."""
    calls: list[tuple[int, int, int, int]] = []
    monkeypatch.setattr(
        win32,
        "CallNextHookEx",
        lambda handle, code, message, data: calls.append((handle, code, message, data))
        or NEXT_HOOK_RESULT,
    )
    return calls


def make(swallow=False, error=None) -> tuple[Recorder, list[str]]:
    lines: list[str] = []
    return Recorder(lines.append, swallow, error), lines


def test_an_event_the_hook_swallows_returns_1_and_stops_the_chain(next_hook):
    hook, lines = make(swallow=True)
    assert hook._callback(win32.HC_ACTION, win32.WM_KEYDOWN, 0x1234) == 1
    assert hook.events == [(win32.WM_KEYDOWN, 0x1234)]
    assert next_hook == []
    assert lines == []


def test_an_event_the_hook_passes_goes_to_the_next_hook(next_hook):
    hook, lines = make(swallow=False)
    assert hook._callback(win32.HC_ACTION, win32.WM_KEYUP, 0x1234) == NEXT_HOOK_RESULT
    assert hook.events == [(win32.WM_KEYUP, 0x1234)]
    assert next_hook == [(0, win32.HC_ACTION, win32.WM_KEYUP, 0x1234)]


@pytest.mark.parametrize("code", [-1, 3, 13])
def test_a_code_other_than_hc_action_is_passed_on_unseen(next_hook, code):
    hook, lines = make(swallow=True)
    assert hook._callback(code, win32.WM_KEYDOWN, 0x1234) == NEXT_HOOK_RESULT
    assert hook.events == [], "the hook must not look at an event Windows told it not to handle"
    assert next_hook == [(0, code, win32.WM_KEYDOWN, 0x1234)]


def test_an_exception_is_logged_and_the_event_passes(next_hook):
    """An exception escaping a hook callback would end the process."""
    hook, lines = make(error=ValueError("bad"))
    assert hook._callback(win32.HC_ACTION, win32.WM_KEYDOWN, 0x1234) == NEXT_HOOK_RESULT
    assert lines == ["Recorder error: ValueError"]
    assert next_hook == [(0, win32.HC_ACTION, win32.WM_KEYDOWN, 0x1234)]


def test_the_log_line_names_the_subclass_not_the_base_class(next_hook):
    hook, lines = make(error=KeyError("x"))
    hook._callback(win32.HC_ACTION, win32.WM_KEYDOWN, 0)
    assert lines == ["Recorder error: KeyError"]


def test_the_callback_windows_receives_is_the_one_the_hook_keeps(monkeypatch):
    """If Python collected the callback, Windows would drop the hook without a word."""
    passed: list[object] = []
    monkeypatch.setattr(
        win32,
        "SetWindowsHookEx",
        lambda kind, callback, module, thread: passed.append(callback) or 0x9999,
    )
    hook, lines = make()
    hook.install()
    assert passed[0] is hook._callback
    assert hook.handle == 0x9999
    assert lines == []

    reference = weakref.ref(passed[0])
    passed.clear()
    gc.collect()
    assert reference() is not None, "the hook must hold the only other reference"

    del hook
    gc.collect()
    assert reference() is None, "and it must be the hook holding it, not something global"


def test_install_passes_the_kind_the_subclass_chose_and_this_module_handle(monkeypatch):
    calls: list[tuple[int, int, int]] = []
    monkeypatch.setattr(
        win32,
        "SetWindowsHookEx",
        lambda kind, callback, module, thread: calls.append((kind, module, thread)) or 0x1,
    )
    hook, _ = make()
    hook.install()
    (kind, module, thread), = calls
    assert kind == win32.WH_KEYBOARD_LL
    assert module == win32.GetModuleHandle(None), "a low-level hook wants this module's handle"
    assert thread == 0, "0 means every thread in the session"


def test_a_failed_install_is_logged_and_leaves_no_handle(monkeypatch):
    monkeypatch.setattr(win32, "SetWindowsHookEx", lambda *args: None)
    hook, lines = make()
    hook.install()
    assert hook.handle == 0
    assert len(lines) == 1
    assert lines[0].startswith("Recorder install failed (error ")


def test_uninstall_unhooks_once_and_forgets_the_handle(monkeypatch):
    unhooked: list[int] = []
    monkeypatch.setattr(win32, "SetWindowsHookEx", lambda *args: 0x4321)
    monkeypatch.setattr(win32, "UnhookWindowsHookEx", lambda handle: unhooked.append(handle) or 1)
    hook, _ = make()
    hook.install()
    hook.uninstall()
    hook.uninstall()
    assert unhooked == [0x4321]
    assert hook.handle == 0


def test_uninstall_without_install_does_nothing(monkeypatch):
    unhooked: list[int] = []
    monkeypatch.setattr(win32, "UnhookWindowsHookEx", lambda handle: unhooked.append(handle) or 1)
    hook, _ = make()
    hook.uninstall()
    assert unhooked == []


def test_the_installed_handle_is_what_reaches_callnexthookex(monkeypatch, next_hook):
    monkeypatch.setattr(win32, "SetWindowsHookEx", lambda *args: 0x4321)
    hook, _ = make()
    hook.install()
    hook._callback(win32.HC_ACTION, win32.WM_KEYUP, 7)
    assert next_hook == [(0x4321, win32.HC_ACTION, win32.WM_KEYUP, 7)]


def test_low_level_hook_cannot_be_used_without_an_on_event():
    with pytest.raises(TypeError):
        LowLevelHook(win32.WH_KEYBOARD_LL, lambda _: None)
