"""Mirrors the HookTranslatorTests class in csharp/tests/GibberishRewriter.App.Tests/HookTests.cs.

That file's KeyStateTrackerTests are already covered, case for case, by test_key_state.py.
"""

from __future__ import annotations

import pytest
from gibberish_rewriter.core.key_names import HoldKeys

from gibberish_rewriter.win import hook_translator, win32


@pytest.mark.parametrize(
    ("message", "expected"),
    [(0x0100, True), (0x0104, True), (0x0101, False), (0x0105, False)],
)
def test_is_key_down_is_true_for_wm_keydown_and_wm_syskeydown(message, expected):
    assert hook_translator.is_key_down(message) is expected


def test_is_key_down_reads_the_names_win32_gives_those_messages():
    assert hook_translator.is_key_down(win32.WM_KEYDOWN)
    assert hook_translator.is_key_down(win32.WM_SYSKEYDOWN)
    assert not hook_translator.is_key_down(win32.WM_KEYUP)
    assert not hook_translator.is_key_down(win32.WM_SYSKEYUP)


def test_is_key_down_ignores_the_high_half_of_a_64_bit_wparam():
    """The C# casts the IntPtr to int before comparing, which keeps only the low 32 bits."""
    assert hook_translator.is_key_down(0x1_0000_0100)
    assert not hook_translator.is_key_down(0x1_0000_0101)


@pytest.mark.parametrize(
    ("flags", "extra_info", "expected"),
    [(0x10, 0x47525752, True), (0x10, 0x12345678, False), (0x00, 0x47525752, False)],
)
def test_is_injected_by_self_needs_the_injected_flag_and_the_app_marker(flags, extra_info, expected):
    assert hook_translator.is_injected_by_self(flags, extra_info) is expected


def test_is_injected_by_self_accepts_the_other_flags_alongside_injected():
    """LLKHF_EXTENDED, LLKHF_ALTDOWN and LLKHF_UP ride in the same field."""
    assert hook_translator.is_injected_by_self(0x10 | 0x01 | 0x20 | 0x80, 0x47525752)


def test_modifiers_reads_shift_ctrl_alt_and_either_win_key():
    assert hook_translator.modifiers(lambda vk: False) is HoldKeys.NONE
    assert hook_translator.modifiers(lambda vk: vk in (0x10, 0x12)) == HoldKeys.SHIFT | HoldKeys.ALT
    assert hook_translator.modifiers(lambda vk: vk in (0x11, 0x5C)) == HoldKeys.CTRL | HoldKeys.WIN
    assert hook_translator.modifiers(lambda vk: vk == 0x5B) == HoldKeys.WIN


def test_modifiers_never_reports_caps_lock():
    """CapsLock is a hold key for chords, but the hook takes it from Engine's own tracking, not from Windows."""
    assert HoldKeys.CAPS_LOCK not in hook_translator.modifiers(lambda vk: True)
    assert hook_translator.modifiers(lambda vk: True) == (
        HoldKeys.SHIFT | HoldKeys.CTRL | HoldKeys.ALT | HoldKeys.WIN
    )


def test_modifiers_asks_only_about_the_five_modifier_codes():
    asked: list[int] = []
    hook_translator.modifiers(lambda vk: asked.append(vk) or False)
    assert asked == [0x10, 0x11, 0x12, 0x5B, 0x5C]


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (0x0201, True),
        (0x0204, True),
        (0x0207, True),
        (0x020B, True),
        (0x0200, False),
        (0x0202, False),
        (0x020A, False),
    ],
)
def test_is_mouse_button_down_is_true_only_for_button_presses(message, expected):
    assert hook_translator.is_mouse_button_down(message) is expected
