"""Mirrors csharp/tests/GibberishRewriter.App.Tests/InputBuilderTests.cs."""

from __future__ import annotations

import pytest
from gibberish_rewriter.core.platform import Shortcut

from gibberish_rewriter.win import input_builder, win32
from gibberish_rewriter.win.win32 import INPUT


def describe(events: list[INPUT]) -> str:
    """"vk" in hex, then v for down or ^ for up, then e when KEYEVENTF_EXTENDEDKEY is set."""
    return " ".join(
        "{:02X}{}{}".format(
            event.u.ki.wVk,
            "^" if event.u.ki.dwFlags & win32.KEYEVENTF_KEYUP else "v",
            "e" if event.u.ki.dwFlags & win32.KEYEVENTF_EXTENDEDKEY else "",
        )
        for event in events
    )


def test_every_event_carries_the_app_marker():
    events = [
        *input_builder.backspaces(1),
        *input_builder.text("a"),
        *input_builder.win_space(),
        *input_builder.key_press(0xE8),
        *input_builder.shortcut(Shortcut.COPY, console=True),
    ]
    assert events
    for event in events:
        assert event.type == win32.INPUT_KEYBOARD
        assert event.u.ki.dwExtraInfo == 0x47525752


def test_the_marker_is_the_four_letters_grwr():
    assert input_builder.EXTRA_INFO.to_bytes(4, "big") == b"GRWR"


def test_backspaces_press_and_release_vk_back():
    assert describe(input_builder.backspaces(2)) == "08v 08^ 08v 08^"
    assert input_builder.backspaces(0) == []


def test_text_sends_each_utf16_unit_as_a_unicode_down_and_up():
    events = input_builder.text("لا😀")
    assert [event.u.ki.wScan for event in events] == [
        0x0644, 0x0644, 0x0627, 0x0627, 0xD83D, 0xD83D, 0xDE00, 0xDE00,
    ]
    assert all(event.u.ki.wVk == 0 for event in events)
    assert [event.u.ki.dwFlags for event in events] == [4, 6, 4, 6, 4, 6, 4, 6]


def test_text_of_the_empty_string_is_no_events():
    assert input_builder.text("") == []


@pytest.mark.parametrize(
    ("shortcut", "console", "expected"),
    [
        (Shortcut.COPY, False, "11v 43v 43^ 11^"),
        (Shortcut.PASTE, False, "11v 56v 56^ 11^"),
        (Shortcut.UNDO, False, "11v 5Av 5A^ 11^"),
        (Shortcut.COPY, True, "11v 2Dve 2D^e 11^"),
        (Shortcut.PASTE, True, "10v 2Dve 2D^e 10^"),
        (Shortcut.UNDO, True, "11v 5Av 5A^ 11^"),
    ],
)
def test_shortcut_uses_insert_variants_in_consoles(shortcut, console, expected):
    assert describe(input_builder.shortcut(shortcut, console)) == expected


def test_win_space_presses_left_win_then_space():
    assert describe(input_builder.win_space()) == "5Bve 20v 20^ 5B^e"


def test_key_press_is_one_down_and_up():
    assert describe(input_builder.key_press(0xE8)) == "E8v E8^"


def test_chunks_hold_at_most_50_events():
    assert [len(chunk) for chunk in input_builder.chunks(input_builder.text("a" * 60))] == [50, 50, 20]


def test_chunks_of_nothing_is_no_chunks():
    assert list(input_builder.chunks([])) == []


def test_chunks_cover_every_event_in_order():
    events = input_builder.text("a" * 60)
    joined = [event for chunk in input_builder.chunks(events) for event in chunk]
    assert [id(event) for event in joined] == [id(event) for event in events]


def test_only_insert_and_the_win_key_are_extended():
    extended = [vk for vk in range(0x100) if input_builder._is_extended(vk)]
    assert extended == [input_builder.VK_INSERT, input_builder.VK_LWIN]


def test_virtual_key_events_leave_the_scan_code_for_inputsender():
    assert all(event.u.ki.wScan == 0 for event in input_builder.key_press(input_builder.VK_BACK))
