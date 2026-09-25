"""The ``layouts`` setting: "auto" or explicit HKL values, checked against the installed layouts. Pure.

Mirrors ``csharp/src/GibberishRewriter.App/Win/LayoutPairResolver.cs``.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from gibberish_rewriter.app import app_messages
from gibberish_rewriter.win import hkl
from gibberish_rewriter.win.hkl import LayoutPair


@dataclass(frozen=True)
class PairResolution:
    """Either a pair or the notification that explains why there is none."""

    pair: LayoutPair | None
    error: str | None


def resolve(
    latin_setting: str, arabic_setting: str, installed: Sequence[tuple[int, str]]
) -> PairResolution:
    """``installed`` is each installed layout with what its KeyA types plain."""
    latin, latin_error = _pick(latin_setting, installed, _is_ascii_letter)
    if latin_error is not None:
        return PairResolution(None, latin_error)
    arabic, arabic_error = _pick(arabic_setting, installed, _is_arabic_letter)
    if arabic_error is not None:
        return PairResolution(None, arabic_error)
    if latin == arabic:
        return PairResolution(None, app_messages.LAYOUTS_SAME)
    return PairResolution(LayoutPair(latin, arabic), None)


def _pick(
    setting: str, installed: Sequence[tuple[int, str]], is_script_letter: Callable[[str], bool]
) -> tuple[int, str | None]:
    if setting == "auto":
        matches = [layout for layout, key_a in installed if len(key_a) == 1 and is_script_letter(key_a)]
        return (matches[0], None) if len(matches) == 1 else (0, app_messages.LAYOUTS_NOT_FOUND)
    # An eight-hex-digit setting that is not hex raises, exactly as C#'s uint.Parse does; ConfigParser has
    # already answered layout.invalid for that case.
    value = hkl.parse(setting)
    if any(layout == value for layout, _ in installed):
        return value, None
    return 0, app_messages.layout_not_installed(setting)


def _is_ascii_letter(c: str) -> bool:
    """C#'s ``char.IsAsciiLetter``."""
    return "A" <= c <= "Z" or "a" <= c <= "z"


def _is_arabic_letter(c: str) -> bool:
    """The same test as TextConverter: U+0600-U+06FF with a letter category."""
    return "\u0600" <= c <= "\u06ff" and unicodedata.category(c).startswith("L")
