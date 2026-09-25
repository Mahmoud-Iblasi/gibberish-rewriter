"""win/keyboard_hook.py. The C# has no KeyboardHookTests: HookTests.cs covers only the pure helpers. The
translation from a KBDLLHOOKSTRUCT to a KeyEvent is where a ctypes port goes wrong, so it is tested here with a
real hook structure in memory, a fake Engine and a fake InputSender. Nothing is hooked and nothing is sent."""

from __future__ import annotations

import ctypes

import pytest
from gibberish_rewriter.core.engine import PASS, KeyDecision, KeyEvent
from gibberish_rewriter.core.key_names import HoldKeys
from gibberish_rewriter.core.key_table import LayoutKind

from gibberish_rewriter.win import foreground, win32
from gibberish_rewriter.win.engine_slot import EngineSlot
from gibberish_rewriter.win.hkl import LayoutPair
from gibberish_rewriter.win.hook_watchdog import HookActivity
from gibberish_rewriter.win.key_state import KeyStateTracker
from gibberish_rewriter.win.keyboard_hook import KeyboardHook

ENGLISH = 0x04090409
ARABIC = 0x04012C01
WINDOW = 0x00BEEF00
PAIR = LayoutPair(ENGLISH, ARABIC)


class FakeEngine:
    """Records every KeyEvent and answers with the decision the test set."""

    def __init__(self, decision: KeyDecision = PASS) -> None:
        self.decision = decision
        self.events: list[KeyEvent] = []

    def on_key(self, event: KeyEvent) -> KeyDecision:
        self.events.append(event)
        return self.decision


class FakeSender:
    """Records the keys the Engine asked for instead of calling SendInput."""

    def __init__(self) -> None:
        self.pressed: list[int] = []

    def key_press(self, vk: int) -> None:
        self.pressed.append(vk)


class Harness:
    """A KeyboardHook with everything around it faked, and the hook structure it reads."""

    def __init__(self, decision: KeyDecision, pair: LayoutPair, slot_present: bool) -> None:
        self.engine = FakeEngine(decision)
        self.sender = FakeSender()
        self.keys = KeyStateTracker()
        self.activity = HookActivity()
        self.lines: list[str] = []
        self.slot = EngineSlot(self.engine, pair) if slot_present else None
        self.hook = KeyboardHook(
            lambda: self.slot, self.sender, self.keys, self.activity, self.lines.append
        )
        self.key = win32.KBDLLHOOKSTRUCT()

    def send(self, message, vk, *, flags=0, extra_info=0, time=1_000):
        self.key.vkCode = vk
        self.key.flags = flags
        self.key.time = time
        self.key.dwExtraInfo = extra_info
        return self.hook.on_event(message, ctypes.addressof(self.key))


@pytest.fixture
def windows(monkeypatch):
    """Pins the foreground window and its layout, and says no modifier is held."""
    monkeypatch.setattr(win32, "GetForegroundWindow", lambda: WINDOW)
    monkeypatch.setattr(win32, "GetAsyncKeyState", lambda vk: 0)
    holder = {"layout": ENGLISH}
    monkeypatch.setattr(foreground, "layout_of", lambda window: holder["layout"])
    return holder


def make(decision: KeyDecision = PASS, pair: LayoutPair = PAIR, slot_present: bool = True) -> Harness:
    return Harness(decision, pair, slot_present)


def test_a_key_down_reaches_the_engine_as_a_key_event(windows):
    harness = make()
    assert harness.send(win32.WM_KEYDOWN, 0x41) is False
    (event,) = harness.engine.events
    assert event == KeyEvent(
        vk=0x41,
        down=True,
        injected_by_self=False,
        is_packet=False,
        modifiers=HoldKeys.NONE,
        window=WINDOW,
        layout=LayoutKind.LATIN,
    )


@pytest.mark.parametrize(
    ("message", "down"),
    [
        (win32.WM_KEYDOWN, True),
        (win32.WM_SYSKEYDOWN, True),
        (win32.WM_KEYUP, False),
        (win32.WM_SYSKEYUP, False),
    ],
)
def test_the_message_decides_down(windows, message, down):
    harness = make()
    harness.send(message, 0x41)
    assert harness.engine.events[0].down is down


def test_every_event_notes_its_time_for_the_watchdog(windows):
    harness = make()
    harness.send(win32.WM_KEYDOWN, 0x41, time=0xFFFF_FF00)
    assert harness.activity.last_event_time == 0xFFFF_FF00


def test_a_key_the_user_pressed_is_tracked_as_down_and_then_up(windows):
    harness = make()
    harness.send(win32.WM_KEYDOWN, 0x14)
    assert harness.keys.is_down(0x14)
    harness.send(win32.WM_KEYUP, 0x14)
    assert not harness.keys.is_down(0x14)


def test_the_apps_own_input_is_marked_and_never_tracked(windows):
    """The tracker is what wait_for_release reads, so it must hold only real presses."""
    harness = make()
    harness.send(win32.WM_KEYDOWN, 0x08, flags=win32.LLKHF_INJECTED, extra_info=0x47525752)
    assert harness.engine.events[0].injected_by_self is True
    assert not harness.keys.is_down(0x08)


def test_another_apps_injected_input_is_not_ours(windows):
    harness = make()
    harness.send(win32.WM_KEYDOWN, 0x08, flags=win32.LLKHF_INJECTED, extra_info=0x12345678)
    assert harness.engine.events[0].injected_by_self is False
    assert harness.keys.is_down(0x08)


def test_vk_packet_is_reported_as_a_packet(windows):
    harness = make()
    harness.send(win32.WM_KEYDOWN, 0xE7)
    assert harness.engine.events[0].is_packet is True
    harness.send(win32.WM_KEYDOWN, 0xE8)
    assert harness.engine.events[1].is_packet is False


def test_the_modifiers_come_from_getasynckeystate(windows, monkeypatch):
    monkeypatch.setattr(win32, "GetAsyncKeyState", lambda vk: -32768 if vk in (0x10, 0x11) else 0)
    harness = make()
    harness.send(win32.WM_KEYDOWN, 0x09)
    assert harness.engine.events[0].modifiers == HoldKeys.SHIFT | HoldKeys.CTRL


def test_a_key_state_with_only_the_toggle_bit_is_not_held(windows, monkeypatch):
    """GetAsyncKeyState's low bit means pressed-since-last-asked, which is not down-now."""
    monkeypatch.setattr(win32, "GetAsyncKeyState", lambda vk: 1)
    harness = make()
    harness.send(win32.WM_KEYDOWN, 0x09)
    assert harness.engine.events[0].modifiers is HoldKeys.NONE


@pytest.mark.parametrize(
    ("layout", "kind"),
    [(ENGLISH, LayoutKind.LATIN), (ARABIC, LayoutKind.ARABIC), (0x04070407, None)],
)
def test_the_foreground_layout_is_mapped_through_the_pair(windows, layout, kind):
    windows["layout"] = layout
    harness = make()
    harness.send(win32.WM_KEYDOWN, 0x41)
    assert harness.engine.events[0].layout is kind


def test_a_sign_extended_layout_handle_still_maps(windows):
    """GetKeyboardLayout hands back the handle sign-extended when its low half has the top bit set."""
    windows["layout"] = 0xFFFFFFFFF0C00409
    harness = make(pair=LayoutPair(ENGLISH, 0xF0C00409))
    harness.send(win32.WM_KEYDOWN, 0x41)
    assert harness.engine.events[0].layout is LayoutKind.ARABIC


def test_a_swallowed_decision_returns_true(windows):
    harness = make(KeyDecision(True))
    assert harness.send(win32.WM_KEYDOWN, 0x14) is True


def test_the_keys_the_engine_asks_for_are_sent_in_order(windows):
    harness = make(KeyDecision(True, (0x14, 0xE8)))
    assert harness.send(win32.WM_KEYUP, 0x09) is True
    assert harness.sender.pressed == [0x14, 0xE8]


def test_nothing_is_sent_when_the_engine_asks_for_nothing(windows):
    harness = make(KeyDecision(False))
    harness.send(win32.WM_KEYDOWN, 0x41)
    assert harness.sender.pressed == []


def test_without_an_engine_the_event_passes_but_is_still_tracked(windows):
    """The slot is empty while the layout pair is unresolved; the hooks stay installed anyway."""
    harness = make(slot_present=False)
    assert harness.send(win32.WM_KEYDOWN, 0x14, time=4_000) is False
    assert harness.keys.is_down(0x14)
    assert harness.activity.last_event_time == 4_000
    assert harness.sender.pressed == []


def test_the_hook_is_registered_for_low_level_keyboard_events(windows):
    assert make().hook._kind == win32.WH_KEYBOARD_LL
