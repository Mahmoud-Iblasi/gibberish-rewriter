"""Converts selected text to the other layout."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from .key_names import ascii_lower
from .key_table import KeyState, KeyTable, LayoutKind
from .word_list import WordList

_PLAIN_THEN_SHIFT = (KeyState.PLAIN, KeyState.SHIFT)
_MAX_SEQUENCES_CHECKED = 6
_WORD_BREAKS = " \t\r\n"


@dataclass(frozen=True)
class Conversion:
    """A converted selection, and the layout its text belongs to now."""

    text: str
    target: LayoutKind


@dataclass(frozen=True)
class _Piece:
    """A converted piece of a word: fixed text, or a two-character sequence one key or two keys could have typed."""

    one_key: str
    two_keys: str | None


def _is_latin_letter(c: str) -> bool:
    return "A" <= c <= "Z" or "a" <= c <= "z"


def _is_arabic_letter(c: str) -> bool:
    return "؀" <= c <= "ۿ" and unicodedata.category(c).startswith("L")


class TextConverter:
    """Converts selected text to the other layout."""

    def __init__(self, table: KeyTable, words: WordList) -> None:
        self._table = table
        self._words = words
        self._latin_typeable: set[str] = set()
        """Every character the Latin layout types."""
        self._arabic_texts: list[tuple[str, str]] = []
        """Every non-empty Arabic text with the Latin text of the same key and state, in table order, plain before shift."""
        for entry in table.keys:
            for text in entry.latin:
                self._latin_typeable.update(text)
            for state in _PLAIN_THEN_SHIFT:
                arabic = entry.text_on(LayoutKind.ARABIC, state)
                if arabic:
                    self._arabic_texts.append((arabic, entry.text_on(LayoutKind.LATIN, state)))

    def convert(self, text: str) -> Conversion | None:
        """Converts text, or returns None when it has no Latin or Arabic letters."""
        latin_letters = 0
        arabic_letters = 0
        last_letter: LayoutKind | None = None
        for c in text:
            if _is_latin_letter(c):
                latin_letters += 1
                last_letter = LayoutKind.LATIN
            elif _is_arabic_letter(c):
                arabic_letters += 1
                last_letter = LayoutKind.ARABIC
        if last_letter is None:
            return None
        if arabic_letters > latin_letters:
            source = LayoutKind.ARABIC
        elif latin_letters > arabic_letters:
            source = LayoutKind.LATIN
        else:
            source = last_letter
        if source is LayoutKind.LATIN:
            return Conversion(self._latin_to_arabic(text, latin_letters), LayoutKind.ARABIC)
        return Conversion(self._arabic_to_latin(text), LayoutKind.LATIN)

    def _latin_to_arabic(self, text: str, latin_letters: int) -> str:
        """Latin text to Arabic: the text was typed on the Latin layout while Arabic was meant."""
        all_caps = latin_letters >= 2 and not any("a" <= c <= "z" for c in text)
        result: list[str] = []
        for c in text:
            upper = "A" <= c <= "Z"
            found = self._table.find(ascii_lower(c) if upper else c, LayoutKind.LATIN)
            if found is None:
                result.append(c)
                continue
            entry, key_state = found
            state = key_state if not upper else KeyState.CAPS if all_caps else KeyState.SHIFT
            arabic = entry.text_on(LayoutKind.ARABIC, state)
            result.append(arabic if arabic else c)
        return "".join(result)

    def _arabic_to_latin(self, text: str) -> str:
        """Arabic text to Latin: the text was typed on the Arabic layout while Latin was meant."""
        result: list[str] = []
        word_start = -1
        for i in range(len(text) + 1):
            at_break = i == len(text) or text[i] in _WORD_BREAKS
            if not at_break:
                if word_start < 0:
                    word_start = i
                continue
            if word_start >= 0:
                result.append(self._convert_word(text[word_start:i]))
                word_start = -1
            if i < len(text):
                result.append(text[i])
        return "".join(result)

    def _convert_word(self, word: str) -> str:
        pieces: list[_Piece] = []
        i = 0
        while i < len(word):
            match = None if word[i] in self._latin_typeable else self._longest_arabic_match(word, i)
            if match is not None:
                arabic, latin = match
                one_key = latin if latin else arabic
                pieces.append(_Piece(one_key, self._two_keys(arabic) if len(arabic) == 2 else None))
                i += len(arabic)
            else:
                pieces.append(_Piece(word[i], None))
                i += 1

        sequences = sum(1 for piece in pieces if piece.two_keys is not None)
        if sequences == 0 or sequences > _MAX_SEQUENCES_CHECKED:
            return _build(pieces, 0, sequences)
        for combination in range(1 << sequences):
            candidate = _build(pieces, combination, sequences)
            if self._is_english_word(candidate):
                return candidate
        return _build(pieces, 0, sequences)

    def _two_keys(self, sequence: str) -> str | None:
        """The sequence read as two keys, or None when a character has no key of its own."""
        first = self._single_character_latin(sequence[0])
        second = self._single_character_latin(sequence[1])
        return None if first is None or second is None else first + second

    def _single_character_latin(self, c: str) -> str | None:
        for arabic, latin in self._arabic_texts:
            if arabic == c and latin:
                return latin
        return None

    def _is_english_word(self, candidate: str) -> bool:
        """ASCII-lowercases, strips leading and trailing characters other than a-z, and checks the word list."""
        lower = ascii_lower(candidate)
        start = 0
        end = len(lower)
        while start < end and not "a" <= lower[start] <= "z":
            start += 1
        while end > start and not "a" <= lower[end - 1] <= "z":
            end -= 1
        return end > start and self._words.contains(lower[start:end])

    def _longest_arabic_match(self, text: str, start: int) -> tuple[str, str] | None:
        """The longest Arabic-layout text starting at start; ties go to the earlier one."""
        best: tuple[str, str] | None = None
        for candidate in self._arabic_texts:
            if len(candidate[0]) > (len(best[0]) if best else 0) and text.startswith(candidate[0], start):
                best = candidate
        return best


def _build(pieces: list[_Piece], combination: int, sequences: int) -> str:
    """Bit 1 reads a sequence as two keys. The leftmost sequence is the most significant bit."""
    parts: list[str] = []
    bit = sequences - 1
    for piece in pieces:
        if piece.two_keys is None:
            parts.append(piece.one_key)
            continue
        parts.append(piece.two_keys if (combination >> bit) & 1 else piece.one_key)
        bit -= 1
    return "".join(parts)
