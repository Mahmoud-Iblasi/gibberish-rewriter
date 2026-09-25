"""Keyboard layout handles as the config file writes them: the low 32 bits as 8 uppercase hex digits.

Mirrors ``csharp/src/GibberishRewriter.App/Win/Hkl.cs``. The C# static class becomes module functions, so
``hkl.low32(...)`` reads beside ``Hkl.Low32(...)``.
"""

from __future__ import annotations

from dataclasses import dataclass

from gibberish_rewriter.core.key_table import LayoutKind

_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")

_UINT_MAX = 0xFFFFFFFF


def low32(handle: int) -> int:
    """The low 32 bits of a layout handle, whether it arrived sign-extended or not."""
    return handle & _UINT_MAX


def format(value: int) -> str:  # noqa: A001 - the C# name is Hkl.Format, and callers write hkl.format(...)
    """8 uppercase hex digits, as the config file writes them."""
    return f"{value:08X}"


def parse(text: str) -> int:
    """Parses 8 hex digits, as ConfigParser accepts them.

    C# uses ``uint.Parse(text, NumberStyles.AllowHexSpecifier)``, which takes hex digits and nothing else: no
    ``0x`` prefix, no sign, no whitespace, no digit separators, and no value above ``uint.MaxValue``. Python's
    ``int(text, 16)`` accepts all of those, so they are rejected here first.
    """
    if not text or any(char not in _HEX_DIGITS for char in text):
        raise ValueError(f"{text!r} is not hex digits.")
    value = int(text, 16)
    if value > _UINT_MAX:
        raise ValueError(f"{text!r} does not fit in 32 bits.")
    return value


def to_handle(value: int) -> int:
    """The handle Windows uses: sign-extended on 64-bit, as GetKeyboardLayoutList returns it.

    C# builds ``new IntPtr(unchecked((int)hkl))``; the number returned here is that handle's ``ToInt64()``, which
    ctypes passes to a ``HKL`` parameter unchanged.
    """
    return value - 0x1_0000_0000 if value & 0x8000_0000 else value


@dataclass(frozen=True)
class LayoutPair:
    """The resolved layout pair, as low 32-bit HKL values."""

    latin: int
    arabic: int

    def kind_of(self, handle: int) -> LayoutKind | None:
        """C# has two overloads, one taking an ``IntPtr`` and one a ``uint``; this one takes either, because
        ``low32`` leaves a value that is already 32-bit alone."""
        value = low32(handle)
        if value == self.latin:
            return LayoutKind.LATIN
        if value == self.arabic:
            return LayoutKind.ARABIC
        return None

    def hkl_of(self, kind: LayoutKind) -> int:
        return self.latin if kind is LayoutKind.LATIN else self.arabic
