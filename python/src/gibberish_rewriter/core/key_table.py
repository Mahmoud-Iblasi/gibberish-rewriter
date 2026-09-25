"""Text per layout, key and state. Loads and saves the JSON snapshot."""

from __future__ import annotations

import enum
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


class LayoutKind(enum.Enum):
    """One side of the layout pair. The value is the name vector files use."""

    LATIN = "latin"
    ARABIC = "arabic"

    def other(self) -> LayoutKind:
        return LayoutKind.ARABIC if self is LayoutKind.LATIN else LayoutKind.LATIN

    @staticmethod
    def parse(name: str) -> LayoutKind:
        if name == "latin":
            return LayoutKind.LATIN
        if name == "arabic":
            return LayoutKind.ARABIC
        raise ValueError(f"Unknown layout '{name}'.")


class KeyState(enum.IntEnum):
    """The modifier state of a key press. The value is the index of the text in the snapshot arrays."""

    PLAIN = 0
    SHIFT = 1
    CAPS = 2
    SHIFT_CAPS = 3


def state_of(shift: bool, caps_on: bool) -> KeyState:
    return KeyState((1 if shift else 0) | (2 if caps_on else 0))


@dataclass(frozen=True)
class KeyEntry:
    """What one key types on each layout, indexed by KeyState. "" means it types nothing."""

    key: str
    vk: int
    latin: tuple[str, ...]
    arabic: tuple[str, ...]

    def text_on(self, layout: LayoutKind, state: KeyState) -> str:
        return (self.latin if layout is LayoutKind.LATIN else self.arabic)[state]


_PLAIN_THEN_SHIFT = (KeyState.PLAIN, KeyState.SHIFT)


class KeyTable:
    """Text per layout, key and state. Loads and saves the JSON snapshot."""

    def __init__(self, latin_hkl: str, arabic_hkl: str, keys: Sequence[KeyEntry]) -> None:
        self.latin_hkl = latin_hkl
        self.arabic_hkl = arabic_hkl
        self.keys: tuple[KeyEntry, ...] = tuple(keys)
        """Keys in table order, the order shared/keys.json lists them in."""
        self._by_vk = {entry.vk: entry for entry in self.keys}

    @classmethod
    def load(cls, path: str | Path) -> KeyTable:
        return cls.parse(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def parse(cls, text: str) -> KeyTable:
        root = json.loads(text)
        keys = [
            KeyEntry(key["key"], key["vk"], _read_texts(key["latin"]), _read_texts(key["arabic"]))
            for key in root["keys"]
        ]
        return cls(root["latinHkl"], root["arabicHkl"], keys)

    def to_json(self) -> str:
        """The snapshot format, one key per line."""

        def quote(text: str) -> str:
            return json.dumps(text, ensure_ascii=False)

        def texts(values: tuple[str, ...]) -> str:
            return "[" + ", ".join(quote(value) for value in values) + "]"

        lines = ["{", f'  "latinHkl": {quote(self.latin_hkl)},', f'  "arabicHkl": {quote(self.arabic_hkl)},', '  "keys": [']
        for index, key in enumerate(self.keys):
            comma = "," if index < len(self.keys) - 1 else ""
            lines.append(
                f'    {{ "key": {quote(key.key)}, "vk": {key.vk}, "latin": {texts(key.latin)}, '
                f'"arabic": {texts(key.arabic)} }}{comma}'
            )
        lines += ["  ]", "}"]
        return "\n".join(lines) + "\n"

    def contains(self, vk: int) -> bool:
        return vk in self._by_vk

    def text_of(self, vk: int, layout: LayoutKind, state: KeyState) -> str:
        """What the key types on the layout in the state; "" if the key isn't in the table or types nothing."""
        entry = self._by_vk.get(vk)
        return entry.text_on(layout, state) if entry is not None else ""

    def find(self, text: str, layout: LayoutKind) -> tuple[KeyEntry, KeyState] | None:
        """The first key in table order that types text, trying plain before shift."""
        if not text:
            return None
        for entry in self.keys:
            for state in _PLAIN_THEN_SHIFT:
                if entry.text_on(layout, state) == text:
                    return entry, state
        return None


def _read_texts(values: list[str]) -> tuple[str, ...]:
    if len(values) != 4:
        raise ValueError("Each layout needs four texts: plain, shift, caps, shiftCaps.")
    return tuple(values)
