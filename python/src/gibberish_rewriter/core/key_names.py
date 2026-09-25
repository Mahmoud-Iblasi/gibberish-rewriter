"""Key names and virtual-key codes, loaded from shared/keys.json."""

from __future__ import annotations

import enum
import json
from pathlib import Path


class HoldKeys(enum.IntFlag):
    """The keys a chord can hold. Flags, so a chord's hold set is one value."""

    NONE = 0
    SHIFT = 1
    CTRL = 2
    ALT = 4
    WIN = 8
    CAPS_LOCK = 16


VK_BACKSPACE = 0x08
VK_CAPS_LOCK = 0x14
VK_PACKET = 0xE7
VK_MASK = 0xE8
"""Unassigned key pressed after an Alt or Win chord fires."""

HOLD_KEY_ORDER = (HoldKeys.SHIFT, HoldKeys.CTRL, HoldKeys.ALT, HoldKeys.WIN, HoldKeys.CAPS_LOCK)
"""The order hold keys are written in (canonical hotkey text)."""

HOLD_KEY_NAMES = {
    HoldKeys.SHIFT: "Shift",
    HoldKeys.CTRL: "Ctrl",
    HoldKeys.ALT: "Alt",
    HoldKeys.WIN: "Win",
    HoldKeys.CAPS_LOCK: "CapsLock",
}
"""Hold-key names as keys.json and hotkey strings write them."""

_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def ascii_lower(text: str) -> str:
    """Lowercases A-Z only."""
    return text.translate(_ASCII_LOWER)


class KeyNames:
    """Key names and virtual-key codes, loaded from shared/keys.json."""

    def __init__(
        self,
        triggers: dict[str, int],
        modifiers: dict[str, int],
        hold_vks: dict[HoldKeys, list[int]],
        table_keys: list[str],
    ) -> None:
        self._triggers = {ascii_lower(name): vk for name, vk in triggers.items()}
        self._modifiers = {ascii_lower(name): vk for name, vk in modifiers.items()}
        self._hold_vks = hold_vks
        self._hold_by_name = {ascii_lower(HOLD_KEY_NAMES[hold]): hold for hold in hold_vks}
        self._hold_by_vk: dict[int, HoldKeys] = {}
        self._modifier_vks: set[int] = set()
        self._name_by_vk: dict[int, str] = {}
        for hold, vks in hold_vks.items():
            for vk in vks:
                self._hold_by_vk[vk] = hold
                self._modifier_vks.add(vk)
        for name, vk in modifiers.items():
            self._modifier_vks.add(vk)
            self._name_by_vk.setdefault(vk, name)
        for name, vk in triggers.items():
            self._name_by_vk.setdefault(vk, name)
        self.table_keys: tuple[str, ...] = tuple(table_keys)
        """The key-table keys in table order, which is also the snapshot's order. LayoutReader reads these."""

    @classmethod
    def load(cls, path: str | Path) -> KeyNames:
        return cls.parse(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def parse(cls, text: str) -> KeyNames:
        root = json.loads(text)
        names_to_hold = {name: hold for hold, name in HOLD_KEY_NAMES.items()}
        hold_vks = {names_to_hold[name]: list(codes) for name, codes in root["holdKeys"].items()}
        triggers = dict(root["keys"])
        table_keys = list(root["tableKeys"])
        lowered = {ascii_lower(name) for name in triggers}
        unknown = next((name for name in table_keys if ascii_lower(name) not in lowered), None)
        if unknown is not None:
            raise ValueError(f'tableKeys lists "{unknown}", which is not in keys.')
        return cls(triggers, dict(root["modifiers"]), hold_vks, table_keys)

    def trigger_vk(self, name: str) -> int | None:
        """Looks up a non-modifier key name, case-insensitively. "`" means Backquote."""
        return self._triggers.get(ascii_lower("Backquote" if name == "`" else name))

    def vk_of(self, name: str) -> int | None:
        """Looks up any key name, modifier or not."""
        vk = self.trigger_vk(name)
        return vk if vk is not None else self._modifiers.get(ascii_lower(name))

    def hold_key(self, name: str) -> HoldKeys | None:
        return self._hold_by_name.get(ascii_lower(name))

    def is_modifier_name(self, name: str) -> bool:
        """True for hold-key names such as Shift and modifier key names such as ShiftLeft or NumLock."""
        lowered = ascii_lower(name)
        return lowered in self._hold_by_name or lowered in self._modifiers

    def is_modifier(self, vk: int) -> bool:
        return vk in self._modifier_vks

    def hold_key_of(self, vk: int) -> HoldKeys:
        return self._hold_by_vk.get(vk, HoldKeys.NONE)

    def vks_of(self, holds: HoldKeys) -> list[int]:
        """Codes of every hold key in holds, in canonical order."""
        return [vk for hold in HOLD_KEY_ORDER if hold in holds for vk in self._hold_vks[hold]]

    def name_of(self, vk: int) -> str:
        return self._name_by_vk.get(vk, f"0x{vk:02X}")
