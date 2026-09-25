"""Button presses are breaks; every event counts as hook activity.

Mirrors ``csharp/src/GibberishRewriter.App/Win/MouseHook.cs``.
"""

from __future__ import annotations

from collections.abc import Callable

from gibberish_rewriter.win import hook_translator, win32
from gibberish_rewriter.win.engine_slot import EngineSlot
from gibberish_rewriter.win.hook_watchdog import HookActivity
from gibberish_rewriter.win.low_level_hook import LowLevelHook
from gibberish_rewriter.win.win32 import MSLLHOOKSTRUCT


class MouseHook(LowLevelHook):
    """WH_MOUSE_LL. Never swallows anything."""

    def __init__(
        self,
        slot: Callable[[], EngineSlot | None],
        activity: HookActivity,
        log: Callable[[str], None],
    ) -> None:
        super().__init__(win32.WH_MOUSE_LL, log)
        self._slot = slot
        self._activity = activity

    def on_event(self, message: int, data: int) -> bool:
        self._activity.note(MSLLHOOKSTRUCT.from_address(data).time)
        if hook_translator.is_mouse_button_down(message):
            current = self._slot()
            if current is not None:
                current.engine.on_mouse_down()
        return False
