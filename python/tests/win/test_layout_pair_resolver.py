"""Mirrors csharp/tests/GibberishRewriter.App.Tests/LayoutPairResolverTests.cs."""

from __future__ import annotations

import pytest

from gibberish_rewriter.win import layout_pair_resolver
from gibberish_rewriter.app.app_messages import LAYOUTS_NOT_FOUND, LAYOUTS_SAME, layout_not_installed
from gibberish_rewriter.win.hkl import LayoutPair
from gibberish_rewriter.win.layout_pair_resolver import resolve

ENGLISH = 0x04090409
ARABIC = 0x04012C01
GERMAN = 0x04070407
RUSSIAN = 0x04190419

USER_LAYOUTS = ((ENGLISH, "a"), (ARABIC, "ش"))
"""English (US) types "a" on KeyA; Arabic (101) types shin."""


def test_auto_picks_the_one_latin_and_the_one_arabic_layout():
    result = resolve("auto", "auto", USER_LAYOUTS)
    assert result.pair == LayoutPair(ENGLISH, ARABIC)
    assert result.error is None


def test_auto_ignores_layouts_of_other_scripts():
    result = resolve("auto", "auto", ((RUSSIAN, "ф"), *USER_LAYOUTS))
    assert result.pair == LayoutPair(ENGLISH, ARABIC)


def test_auto_with_two_latin_layouts_asks_for_explicit_values():
    result = resolve("auto", "auto", ((GERMAN, "a"), *USER_LAYOUTS))
    assert result.pair is None
    assert result.error == LAYOUTS_NOT_FOUND


def test_auto_without_an_arabic_layout_asks_for_explicit_values():
    assert resolve("auto", "auto", ((ENGLISH, "a"),)).error == LAYOUTS_NOT_FOUND


def test_an_explicit_value_chooses_among_several_latin_layouts():
    result = resolve("04070407", "auto", ((GERMAN, "a"), *USER_LAYOUTS))
    assert result.pair == LayoutPair(GERMAN, ARABIC)


def test_an_explicit_layout_that_is_not_installed_keeps_the_app_disabled():
    assert resolve("040C040C", "auto", USER_LAYOUTS).error == layout_not_installed("040C040C")


def test_the_same_layout_twice_is_rejected():
    assert resolve("04090409", "04090409", USER_LAYOUTS).error == LAYOUTS_SAME


def test_the_latin_setting_is_reported_before_the_arabic_one():
    """The C# returns on the first error, so a config with two bad values names the first."""
    result = resolve("040C040C", "040D040D", USER_LAYOUTS)
    assert result.error == layout_not_installed("040C040C")


def test_an_explicit_value_is_matched_case_insensitively():
    """Hkl.Parse takes hex digits in either case, as ConfigParser accepts them."""
    assert resolve("auto", "04012c01", USER_LAYOUTS).pair == LayoutPair(ENGLISH, ARABIC)


def test_a_setting_that_is_not_hex_raises_as_uint_parse_does():
    """ConfigParser has already answered layout.invalid for this, so the resolver never sees it in the app."""
    with pytest.raises(ValueError):
        resolve("nonsense", "auto", USER_LAYOUTS)


@pytest.mark.parametrize("key_a", ["", "ab", "1", "-", " "])
def test_auto_ignores_a_key_a_that_is_not_one_letter(key_a):
    """A dead KeyA comes back as "", and a layout whose KeyA types a digit is no help either."""
    assert resolve("auto", "auto", ((ENGLISH, key_a), (ARABIC, "ش"))).error == LAYOUTS_NOT_FOUND


def test_auto_finds_no_arabic_layout_when_key_a_types_an_arabic_digit():
    """U+0660 is in the Arabic block but is a number, not a letter."""
    assert resolve("auto", "auto", ((ENGLISH, "a"), (ARABIC, "٠"))).error == LAYOUTS_NOT_FOUND


@pytest.mark.parametrize("key_a", ["ش", "ب", "ى", "ی"])
def test_every_arabic_letter_in_the_block_counts(key_a):
    assert resolve("auto", "auto", ((ENGLISH, "a"), (ARABIC, key_a))).pair == LayoutPair(ENGLISH, ARABIC)


@pytest.mark.parametrize("key_a", ["a", "A", "z", "Q"])
def test_every_ascii_letter_counts_as_latin(key_a):
    assert resolve("auto", "auto", ((ENGLISH, key_a), (ARABIC, "ش"))).pair is not None


def test_a_latin_letter_outside_ascii_does_not_count():
    """char.IsAsciiLetter is a-z and A-Z only, so an accented layout needs an explicit HKL."""
    assert resolve("auto", "auto", ((GERMAN, "ä"), (ARABIC, "ش"))).error == LAYOUTS_NOT_FOUND


def test_no_layouts_at_all_asks_for_explicit_values():
    assert resolve("auto", "auto", ()).error == LAYOUTS_NOT_FOUND


def test_two_explicit_values_need_no_key_a_at_all():
    """A layout whose KeyA is a dead key can still be named explicitly."""
    result = resolve("04090409", "04012C01", ((ENGLISH, ""), (ARABIC, "")))
    assert result.pair == LayoutPair(ENGLISH, ARABIC)
    assert result.error is None


def test_the_texts_are_the_ones_the_c_sharp_app_shows():
    """app_messages holds them, as AppMessages.cs does; the resolver must not word them itself."""
    assert LAYOUTS_NOT_FOUND == (
        'Couldn\'t find exactly one Latin and one Arabic keyboard layout. Set "layouts" in the config file to '
        'HKL values such as "04090409" and "04012C01". Gibberish Rewriter stays disabled until then.'
    )
    assert LAYOUTS_SAME == (
        "layouts.latin and layouts.arabic are the same layout. "
        "Gibberish Rewriter stays disabled until they differ."
    )
    assert layout_not_installed("040C040C") == (
        "The keyboard layout 040C040C in the config file isn't installed. "
        "Gibberish Rewriter stays disabled until it is."
    )


def test_a_resolution_is_a_pair_or_an_error_and_never_both():
    for result in (
        resolve("auto", "auto", USER_LAYOUTS),
        resolve("auto", "auto", ()),
        resolve("04090409", "04090409", USER_LAYOUTS),
    ):
        assert (result.pair is None) != (result.error is None)


def test_the_resolver_never_touches_windows():
    """It is pure: the C# marks it so, and the whole point is that a config reload can run it anywhere."""
    assert "win32" not in vars(layout_pair_resolver)
    assert not hasattr(layout_pair_resolver, "LAYOUTS_SAME"), "the texts live in app_messages"
