"""Which keys are physically down, as the keyboard hook saw them.

Windows' own key state never shows swallowed keys (CapsLock, a chord's trigger), so ``wait_for_release`` checks this
too. Mirrors ``csharp/src/GibberishRewriter.App/Win/KeyStateTracker.cs``.
"""

from __future__ import annotations

_SIZE = 256
"""The C# tracks a ``bool[256]``; a virtual-key code outside it is ignored rather than raising."""


class KeyStateTracker:
    """Read from the action thread, written from the hook thread; both only ever touch one byte."""

    def __init__(self) -> None:
        self._down = bytearray(_SIZE)

    def set(self, vk: int, down: bool) -> None:
        if 0 <= vk < _SIZE:
            self._down[vk] = 1 if down else 0

    def is_down(self, vk: int) -> bool:
        return 0 <= vk < _SIZE and bool(self._down[vk])

    def clear(self) -> None:
        """After a hook reinstall or an unlock, when key-ups may have been missed."""
        self._down[:] = bytes(_SIZE)
