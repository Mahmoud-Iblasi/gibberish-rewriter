"""Detects chords, swallows their keys and replays CapsLock taps."""

from __future__ import annotations

import enum
from dataclasses import dataclass

from .config import Chord
from .key_names import VK_CAPS_LOCK, HoldKeys, KeyNames


class ChordAction(enum.Enum):
    FIX_TYPED = "fix_typed"
    FIX_SELECTION = "fix_selection"


@dataclass(frozen=True)
class ChordDecision:
    """What to do with one key event.

    swallow: Keep the event from reaching Windows.
    fired: The chord this key-down fired.
    replay_caps_lock: Send one CapsLock press so Caps Lock toggles.
    send_mask_key: Send one press of VK_MASK so Alt or Win don't open menus.
    caps_lock_toggled: A CapsLock press reaches Windows because of this event.
    """

    swallow: bool
    fired: ChordAction | None = None
    replay_caps_lock: bool = False
    send_mask_key: bool = False
    caps_lock_toggled: bool = False


PASS = ChordDecision(False)
SWALLOW_KEY = ChordDecision(True)


class ChordDetector:
    """Detects chords, swallows their keys and replays CapsLock taps. Engine serializes calls."""

    def __init__(self, names: KeyNames, fix_typed: Chord, fix_selection: Chord) -> None:
        self._names = names
        self._caps_lock_down = False
        self._chord_fired_while_caps_lock_down = False
        self._swallowed_triggers: set[int] = set()
        self.set_chords(fix_typed, fix_selection)

    @property
    def caps_lock_down(self) -> bool:
        """True while CapsLock is physically held."""
        return self._caps_lock_down

    @property
    def _caps_lock_is_hold_key(self) -> bool:
        return (self._fix_typed.hold | self._fix_selection.hold) & HoldKeys.CAPS_LOCK != 0

    def set_chords(self, fix_typed: Chord, fix_selection: Chord) -> None:
        """Replaces the chords and forgets any half-pressed chord."""
        self._fix_typed = fix_typed
        self._fix_selection = fix_selection
        self._caps_lock_down = False
        self._chord_fired_while_caps_lock_down = False
        self._swallowed_triggers.clear()

    def on_key(self, vk: int, down: bool, modifiers: HoldKeys) -> ChordDecision:
        """Decides one key event this app did not inject.

        modifiers: Shift, Ctrl, Alt and Win as Windows reports them just before the event.
        """
        if vk in self._swallowed_triggers:
            if not down:
                self._swallowed_triggers.discard(vk)
            return SWALLOW_KEY

        if vk == VK_CAPS_LOCK:
            return self._on_caps_lock(down)

        if not down or self._names.is_modifier(vk):
            return PASS

        held = (modifiers & ~HoldKeys.CAPS_LOCK) | (HoldKeys.CAPS_LOCK if self._caps_lock_down else HoldKeys.NONE)
        if self._fix_typed.trigger_vk == vk and self._fix_typed.hold == held:
            action, chord = ChordAction.FIX_TYPED, self._fix_typed
        elif self._fix_selection.trigger_vk == vk and self._fix_selection.hold == held:
            action, chord = ChordAction.FIX_SELECTION, self._fix_selection
        else:
            return PASS

        self._swallowed_triggers.add(vk)
        if self._caps_lock_down:
            self._chord_fired_while_caps_lock_down = True
        return ChordDecision(True, action, send_mask_key=chord.hold & (HoldKeys.ALT | HoldKeys.WIN) != 0)

    def _on_caps_lock(self, down: bool) -> ChordDecision:
        if not self._caps_lock_is_hold_key:
            toggled = down and not self._caps_lock_down
            self._caps_lock_down = down
            return ChordDecision(False, caps_lock_toggled=toggled)

        if down:
            if not self._caps_lock_down:
                self._caps_lock_down = True
                self._chord_fired_while_caps_lock_down = False
            return SWALLOW_KEY

        replay = self._caps_lock_down and not self._chord_fired_while_caps_lock_down
        self._caps_lock_down = False
        return ChordDecision(True, replay_caps_lock=replay, caps_lock_toggled=replay)
