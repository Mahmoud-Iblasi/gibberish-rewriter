"""Lowercase English words from shared/wordlists/english.txt."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


class WordList:
    def __init__(self, words: set[str]) -> None:
        self._words = words

    @classmethod
    def load(cls, path: str | Path) -> WordList:
        with open(path, encoding="utf-8-sig") as lines:
            return cls.from_words(lines)

    @classmethod
    def from_words(cls, words: Iterable[str]) -> WordList:
        return cls({word.strip() for word in words if word.strip()})

    @property
    def count(self) -> int:
        return len(self._words)

    def contains(self, word: str) -> bool:
        """Exact, case-sensitive lookup. The list holds lowercase words, so lowercase first."""
        return word in self._words
