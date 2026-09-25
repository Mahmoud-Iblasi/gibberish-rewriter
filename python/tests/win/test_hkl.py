"""Mirrors csharp/tests/GibberishRewriter.App.Tests/HklTests.cs."""

from __future__ import annotations

import ctypes

import pytest
from gibberish_rewriter.core.key_table import LayoutKind

from gibberish_rewriter.win import hkl
from gibberish_rewriter.win.hkl import LayoutPair

SIGN_EXTENDED = 0xFFFFFFFFF0C00409
"""What GetKeyboardLayoutList hands back for Arabic on a machine with a layout handle above 0x80000000."""


def test_low32_drops_the_sign_extension_of_64_bit_handles():
    assert hkl.low32(SIGN_EXTENDED) == 0xF0C00409
    assert hkl.low32(SIGN_EXTENDED - 2**64) == 0xF0C00409
    assert hkl.low32(0x04090409) == 0x04090409


def test_to_handle_sign_extends_like_getkeyboardlayoutlist():
    assert hkl.to_handle(0xF0C00409) == SIGN_EXTENDED - 2**64
    assert hkl.to_handle(0x04090409) == 0x04090409


def test_to_handle_reaches_win32_with_every_bit_set():
    """ctypes passes the negative number to an HKL parameter as the full 64-bit handle."""
    assert ctypes.c_void_p(hkl.to_handle(0xF0C00409)).value == SIGN_EXTENDED
    assert ctypes.c_void_p(hkl.to_handle(0x04090409)).value == 0x04090409


@pytest.mark.parametrize(
    ("value", "text"),
    [(0x04090409, "04090409"), (0x04012C01, "04012C01"), (0xF0C00409, "F0C00409")],
)
def test_format_and_parse_round_trip(value, text):
    assert hkl.format(value) == text
    assert hkl.parse(text) == value
    assert hkl.parse(text.lower()) == value


def test_low32_and_to_handle_round_trip():
    for value in (0x04090409, 0x04012C01, 0xF0C00409, 0xFFFFFFFF, 0x00000000):
        assert hkl.low32(hkl.to_handle(value)) == value


@pytest.mark.parametrize("text", ["0x04090409", "+4090409", "-4090409", "0409_0409", "", " 04090409", "1FFFFFFFF", "0409040G"])
def test_parse_rejects_what_uint_parse_rejects(text):
    """uint.Parse with NumberStyles.AllowHexSpecifier takes hex digits and nothing else."""
    with pytest.raises(ValueError):
        hkl.parse(text)


def test_layout_pair_maps_handles_to_kinds():
    pair = LayoutPair(0x04090409, 0x04012C01)
    assert pair.kind_of(0x04090409) is LayoutKind.LATIN
    assert pair.kind_of(0x04012C01) is LayoutKind.ARABIC
    assert pair.kind_of(0x04070407) is None
    assert pair.hkl_of(LayoutKind.ARABIC) == 0x04012C01
    assert pair.hkl_of(LayoutKind.LATIN) == 0x04090409


def test_layout_pair_accepts_a_sign_extended_handle():
    pair = LayoutPair(0x04090409, 0xF0C00409)
    assert pair.kind_of(SIGN_EXTENDED) is LayoutKind.ARABIC
    assert pair.kind_of(SIGN_EXTENDED - 2**64) is LayoutKind.ARABIC
