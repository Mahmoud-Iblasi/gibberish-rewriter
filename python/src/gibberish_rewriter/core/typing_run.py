"""The keys typed since the last break. Engine serializes access."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .key_table import KeyState, KeyTable, LayoutKind


@dataclass(frozen=True)
class KeyRecord:
    """One recorded key press: what it typed, and what the same key and state type on the other layout."""

    vk: int
    shift: bool
    caps_on: bool
    text: str
    other_text: str


class TypingRun:
    """The keys typed since the last break. Engine serializes access."""

    def __init__(self, max_length: int) -> None:
        self._records: list[KeyRecord] = []
        self._max_length = max_length
        self._window = 0
        self._layout = LayoutKind.LATIN
        self._sealed = False

    @property
    def max_length(self) -> int:
        """The most records kept. Lowering it drops the oldest records."""
        return self._max_length

    @max_length.setter
    def max_length(self, value: int) -> None:
        if value < 0:
            raise ValueError(f"max_length must not be negative, was {value}.")
        self._max_length = value
        self._drop_oldest()

    @property
    def window(self) -> int:
        return self._window

    @property
    def layout(self) -> LayoutKind:
        return self._layout

    @property
    def is_empty(self) -> bool:
        return len(self._records) == 0

    @property
    def sealed(self) -> bool:
        """True after a fix: the run is kept only for undo."""
        return self._sealed

    @property
    def records(self) -> tuple[KeyRecord, ...]:
        """A snapshot of the records, not the live list (the C# returns the live list as a read-only view)."""
        return tuple(self._records)

    @property
    def text(self) -> str:
        return "".join(record.text for record in self._records)

    @property
    def other_text(self) -> str:
        return "".join(record.other_text for record in self._records)

    def clear(self) -> None:
        self._records.clear()
        self._sealed = False

    def record(self, window: int, layout: LayoutKind, key_record: KeyRecord) -> None:
        """Adds a record, first clearing the run if it is sealed or belongs to another window or layout."""
        if not self.is_empty and (self._sealed or window != self._window or layout is not self._layout):
            self.clear()
        if self.is_empty:
            self._window = window
            self._layout = layout
        self._records.append(key_record)
        self._drop_oldest()

    def backspace(self, table: KeyTable) -> None:
        """Removes the last character of the run's text, as the app did. Measures and trims in Python
        characters where the C# uses UTF-16 units; every text the key table can produce is in the basic plane, so
        the two agree."""
        if self.is_empty:
            return
        if self._sealed:
            self.clear()
            return

        last = self._records.pop()
        if len(last.text) <= 1:
            return

        remaining = last.text[:-1]
        found = table.find(remaining, self._layout)
        if found is None:
            self.clear()
            return
        entry, state = found
        other = entry.text_on(self._layout.other(), state)
        self._records.append(
            KeyRecord(entry.vk, state is KeyState.SHIFT, False, remaining, other if other else remaining)
        )

    def swap_after_fix(self) -> None:
        """After a fix: the run now describes the fixed text, on the other layout, kept only for undo."""
        if self.is_empty:
            return
        for index, record in enumerate(self._records):
            self._records[index] = replace(record, text=record.other_text, other_text=record.text)
        self._layout = self._layout.other()
        self._sealed = True

    def _drop_oldest(self) -> None:
        if len(self._records) > self._max_length:
            del self._records[: len(self._records) - self._max_length]
