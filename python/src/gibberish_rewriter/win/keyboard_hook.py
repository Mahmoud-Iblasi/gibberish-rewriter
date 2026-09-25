"""Forwards key events to Engine, sends the keys it asks for, swallows when told.

Mirrors ``csharp/src/GibberishRewriter.App/Win/KeyboardHook.cs``.
"""

from __future__ import annotations

from collections.abc import Callable

from gibberish_rewriter.core.engine import KeyEvent
from gibberish_rewriter.core.key_names import VK_PACKET

from gibberish_rewriter.win import foreground, hook_translator, win32
from gibberish_rewriter.win.engine_slot import EngineSlot
from gibberish_rewriter.win.hook_watchdog import HookActivity
from gibberish_rewriter.win.input_sender import InputSender
from gibberish_rewriter.win.key_state import KeyStateTracker
from gibberish_rewriter.win.low_level_hook import LowLevelHook
from gibberish_rewriter.win.win32 import KBDLLHOOKSTRUCT


class KeyboardHook(LowLevelHook):
    """WH_KEYBOARD_LL. Every callback runs on the hook thread and must return well inside Windows' 1 s limit."""

    def __init__(
        self,
        slot: Callable[[], EngineSlot | None],
        sender: InputSender,
        keys: KeyStateTracker,
        activity: HookActivity,
        log: Callable[[str], None],
    ) -> None:
        super().__init__(win32.WH_KEYBOARD_LL, log)
        self._slot = slot
        self._sender = sender
        self._keys = keys
        self._activity = activity

    def on_event(self, message: int, data: int) -> bool:
        # A view on Windows' own KBDLLHOOKSTRUCT, where the C# copies it out with Marshal.PtrToStructure; the
        # memory belongs to the hook and does not change while the callback runs.
        key = KBDLLHOOKSTRUCT.from_address(data)
        self._activity.note(key.time)
        vk = key.vkCode
        down = hook_translator.is_key_down(message)
        injected_by_self = hook_translator.is_injected_by_self(key.flags, key.dwExtraInfo)
        if not injected_by_self:
            self._keys.set(vk, down)
        current = self._slot()
        if current is None:
            return False

        window = win32.GetForegroundWindow() or 0
        layout = foreground.layout_of(window)
        decision = current.engine.on_key(
            KeyEvent(
                vk,
                down,
                injected_by_self,
                vk == VK_PACKET,
                hook_translator.modifiers(_is_down_now),
                window,
                current.pair.kind_of(layout),
            )
        )
        for send in decision.send_keys:
            self._sender.key_press(send)
        return decision.swallow


def _is_down_now(vk: int) -> bool:
    """Inside the hook, GetAsyncKeyState still shows the state before the current key."""
    return win32.GetAsyncKeyState(vk) < 0
