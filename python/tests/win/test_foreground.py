"""Mirrors csharp/tests/GibberishRewriter.App.Tests/ForegroundTests.cs, and adds what a ctypes port can get
wrong that C#'s marshaller cannot: the class-name buffer and the elevation handles. Every Win32 call made here is
read-only, so no desktop and no integration flag are needed."""

from __future__ import annotations

import ctypes
import os

import pytest
from gibberish_rewriter.core.key_table import LayoutKind

from gibberish_rewriter.win import foreground, hkl, layout_reader, win32
from gibberish_rewriter.win.hkl import LayoutPair

PAIR = LayoutPair(0x04090409, 0x04012C01)


@pytest.mark.parametrize(
    ("class_name", "expected"),
    [
        ("ConsoleWindowClass", True),
        ("CASCADIA_HOSTING_WINDOW_CLASS", True),
        ("Chrome_WidgetWin_1", False),
        ("Notepad", False),
        ("consolewindowclass", False),
    ],
)
def test_is_console_class_matches_the_two_console_classes_exactly(class_name, expected):
    assert foreground.is_console_class(class_name) is expected


def test_is_console_class_is_not_a_prefix_or_substring_test():
    assert not foreground.is_console_class("")
    assert not foreground.is_console_class("ConsoleWindowClass2")
    assert not foreground.is_console_class("XConsoleWindowClass")


def test_no_window_is_not_blocked_by_elevation():
    assert foreground.is_blocked_by_elevation(0) is False


def test_the_class_name_of_no_window_is_empty():
    """GetClassName returns 0 for a handle that is not a window; the C# floors the length at 0."""
    assert foreground.class_name_of(0) == ""


def test_the_class_name_buffer_holds_255_characters_and_a_terminator():
    """cchMaxCount counts the terminator, so a 256-unit buffer returns at most 255 characters."""
    assert foreground.CLASS_NAME_LENGTH == 256
    buffer = ctypes.create_unicode_buffer(foreground.CLASS_NAME_LENGTH)
    assert len(buffer) == 256


def test_is_privileged_process_answers_for_this_process():
    """A read of this process's own token: it changes nothing and always has an answer."""
    assert foreground.is_privileged_process() in (True, False)


def test_this_process_does_not_block_itself_unless_it_is_elevated():
    """The elevation test is the same question the app asks about a foreground window."""
    assert foreground._is_process_elevated(os.getpid()) == foreground.is_privileged_process()


def test_a_process_id_that_does_not_exist_is_not_elevated():
    """OpenProcess fails with ERROR_INVALID_PARAMETER, not access denied, so the answer is no."""
    assert foreground._is_process_elevated(0xFFFFFFF0) is False


def test_the_layout_of_this_thread_is_one_of_the_installed_layouts():
    """GetWindowThreadProcessId(NULL) is 0, which GetKeyboardLayout reads as this thread."""
    assert hkl.low32(foreground.layout_of(0)) in layout_reader.installed_layouts()


def test_read_answers_every_question_engine_asks_about_the_foreground_window():
    window = foreground.read(PAIR)
    assert isinstance(window.window, int)
    assert window.layout is None or isinstance(window.layout, LayoutKind)
    assert isinstance(window.is_console, bool)
    assert isinstance(window.is_blocked_by_elevation, bool)


def test_read_asks_win32_in_the_order_the_c_sharp_does(monkeypatch):
    """One GetForegroundWindow, then the layout, the class name and the elevation of that same handle."""
    asked: list[tuple[str, int]] = []
    monkeypatch.setattr(win32, "GetForegroundWindow", lambda: 0x1234)
    monkeypatch.setattr(
        foreground, "layout_of", lambda window: asked.append(("layout", window)) or 0x04012C01
    )
    monkeypatch.setattr(
        foreground,
        "class_name_of",
        lambda window: asked.append(("class", window)) or "ConsoleWindowClass",
    )
    monkeypatch.setattr(
        foreground, "is_blocked_by_elevation", lambda window: asked.append(("elevation", window)) or True
    )
    window = foreground.read(PAIR)
    assert asked == [("layout", 0x1234), ("class", 0x1234), ("elevation", 0x1234)]
    assert window.window == 0x1234
    assert window.layout is LayoutKind.ARABIC
    assert window.is_console is True
    assert window.is_blocked_by_elevation is True


def test_read_survives_there_being_no_foreground_window(monkeypatch):
    """GetForegroundWindow returns NULL while a screen saver or the lock screen is up."""
    monkeypatch.setattr(win32, "GetForegroundWindow", lambda: None)
    window = foreground.read(PAIR)
    assert window.window == 0
    assert window.is_console is False
    assert window.is_blocked_by_elevation is False


def test_a_layout_outside_the_pair_is_reported_as_neither(monkeypatch):
    monkeypatch.setattr(win32, "GetForegroundWindow", lambda: 0x1234)
    monkeypatch.setattr(foreground, "layout_of", lambda window: 0x04070407)
    monkeypatch.setattr(foreground, "class_name_of", lambda window: "Notepad")
    monkeypatch.setattr(foreground, "is_blocked_by_elevation", lambda window: False)
    assert foreground.read(PAIR).layout is None
