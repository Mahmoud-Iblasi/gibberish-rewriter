"""win/mouse_hook.py. The C# has no MouseHookTests; the hook reads an MSLLHOOKSTRUCT, whose four bytes of
padding before dwExtraInfo make the wrong offset for `time` an easy mistake, so a real structure is read here."""

from __future__ import annotations

import ctypes

import pytest

from gibberish_rewriter.win import win32
from gibberish_rewriter.win.engine_slot import EngineSlot
from gibberish_rewriter.win.hkl import LayoutPair
from gibberish_rewriter.win.hook_watchdog import HookActivity
from gibberish_rewriter.win.mouse_hook import MouseHook

PAIR = LayoutPair(0x04090409, 0x04012C01)


class FakeEngine:
    """Counts the breaks a mouse press asks for."""

    def __init__(self) -> None:
        self.mouse_downs = 0

    def on_mouse_down(self) -> None:
        self.mouse_downs += 1


class Harness:
    def __init__(self, slot_present: bool = True) -> None:
        self.engine = FakeEngine()
        self.activity = HookActivity()
        self.lines: list[str] = []
        self.slot = EngineSlot(self.engine, PAIR) if slot_present else None
        self.hook = MouseHook(lambda: self.slot, self.activity, self.lines.append)
        self.mouse = win32.MSLLHOOKSTRUCT()

    def send(self, message: int, time: int = 2_000) -> bool:
        self.mouse.time = time
        return self.hook.on_event(message, ctypes.addressof(self.mouse))


@pytest.mark.parametrize(
    "message",
    [win32.WM_LBUTTONDOWN, win32.WM_RBUTTONDOWN, win32.WM_MBUTTONDOWN, win32.WM_XBUTTONDOWN],
)
def test_a_button_press_breaks_the_run(message):
    harness = Harness()
    assert harness.send(message) is False
    assert harness.engine.mouse_downs == 1


@pytest.mark.parametrize("message", [0x0200, 0x0202, 0x020A, 0x0205])
def test_a_move_a_release_and_a_wheel_turn_are_not_breaks(message):
    harness = Harness()
    assert harness.send(message) is False
    assert harness.engine.mouse_downs == 0


def test_every_event_notes_its_time_for_the_watchdog():
    """The mouse hook's job is as much to prove the hooks are alive as to report clicks."""
    harness = Harness()
    harness.send(0x0200, time=7_777)
    assert harness.activity.last_event_time == 7_777
    harness.send(win32.WM_LBUTTONDOWN, time=0xFFFF_FF00)
    assert harness.activity.last_event_time == 0xFFFF_FF00


def test_the_mouse_hook_never_swallows_anything():
    harness = Harness()
    assert not any(harness.send(message) for message in range(0x0200, 0x0210))


def test_without_an_engine_a_press_is_still_noted():
    harness = Harness(slot_present=False)
    assert harness.send(win32.WM_LBUTTONDOWN, time=55) is False
    assert harness.activity.last_event_time == 55


def test_the_hook_is_registered_for_low_level_mouse_events():
    assert Harness().hook._kind == win32.WH_MOUSE_LL
