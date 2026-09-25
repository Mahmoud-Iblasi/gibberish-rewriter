"""Mirrors csharp/tests/GibberishRewriter.App.Tests/LayoutSwitcherTests.cs, which covers only NeedsWinSpace.

Switch itself asks the foreground window to change layout, so it is exercised here with PostMessage and the
layout read both replaced: a real run would change the layout of whatever window the user is in.
"""

from __future__ import annotations

import pytest

from gibberish_rewriter.win import foreground, hkl, layout_switcher, win32
from gibberish_rewriter.win.layout_switcher import LayoutSwitcher, needs_win_space

ENGLISH = 0x04090409
ARABIC = 0x04012C01
WINDOW = 0x00BEEF00


@pytest.mark.parametrize(
    ("current", "target", "installed", "expected"),
    [(ENGLISH, ARABIC, 2, True), (ENGLISH, ARABIC, 3, False), (ARABIC, ARABIC, 2, False)],
)
def test_win_space_only_when_the_switch_failed_and_two_layouts_are_installed(
    current, target, installed, expected
):
    assert needs_win_space(current, target, installed) is expected


def test_win_space_is_useless_with_one_layout_installed():
    assert needs_win_space(ENGLISH, ARABIC, 1) is False


class FakeSender:
    def __init__(self) -> None:
        self.win_spaces = 0

    def win_space(self) -> None:
        self.win_spaces += 1


class Harness:
    """A switcher whose PostMessage goes nowhere and whose layout read answers what the test says."""

    def __init__(self, monkeypatch, after: int, installed_count: int = 2) -> None:
        self.posted: list[tuple[int, int, int, int]] = []
        self.slept: list[int] = []
        self.lines: list[str] = []
        self.sender = FakeSender()
        monkeypatch.setattr(win32, "GetForegroundWindow", lambda: WINDOW)
        monkeypatch.setattr(
            win32,
            "PostMessage",
            lambda window, message, wparam, lparam: self.posted.append(
                (window, message, wparam, lparam)
            )
            or 1,
        )
        monkeypatch.setattr(win32, "GetKeyboardLayoutList", lambda size, buffer: installed_count)
        monkeypatch.setattr(foreground, "layout_of", lambda window: after)
        self.switcher = LayoutSwitcher(self.sender, self.lines.append, self.slept.append)


def test_a_switch_that_works_is_logged_and_sends_nothing(monkeypatch):
    harness = Harness(monkeypatch, after=ARABIC)
    harness.switcher.switch(ARABIC)
    assert harness.sender.win_spaces == 0
    assert harness.lines == ["Switched the layout to 04012C01"]


def test_the_request_goes_to_the_foreground_window_as_a_layout_handle(monkeypatch):
    harness = Harness(monkeypatch, after=ARABIC)
    harness.switcher.switch(ARABIC)
    assert harness.posted == [(WINDOW, win32.WM_INPUTLANGCHANGEREQUEST, 0, hkl.to_handle(ARABIC))]


def test_a_high_layout_handle_is_posted_sign_extended(monkeypatch):
    """C#'s IntPtr(unchecked((int)hkl)) sign-extends from 32 bits, and LPARAM carries the negative number."""
    harness = Harness(monkeypatch, after=0xF0C00409)
    harness.switcher.switch(0xF0C00409)
    assert harness.posted[0][3] == 0xF0C00409 - 2**32 < 0


def test_the_layout_is_checked_after_a_pause(monkeypatch):
    harness = Harness(monkeypatch, after=ARABIC)
    harness.switcher.switch(ARABIC)
    assert harness.slept == [layout_switcher.CHECK_DELAY_MS]
    assert layout_switcher.CHECK_DELAY_MS == 200


def test_a_switch_that_failed_falls_back_to_win_space(monkeypatch):
    harness = Harness(monkeypatch, after=ENGLISH, installed_count=2)
    harness.switcher.switch(ARABIC)
    assert harness.sender.win_spaces == 1
    assert harness.lines == ["The layout stayed 04090409; sent Win+Space"]


def test_with_three_layouts_installed_it_gives_up_rather_than_guessing(monkeypatch):
    """Win+Space cycles, so with three layouts it could land anywhere."""
    harness = Harness(monkeypatch, after=ENGLISH, installed_count=3)
    harness.switcher.switch(ARABIC)
    assert harness.sender.win_spaces == 0
    assert harness.lines == ["The layout stayed 04090409; couldn't switch to 04012C01"]


def test_the_installed_count_is_asked_for_with_a_null_buffer(monkeypatch):
    asked: list[tuple[int, object]] = []
    harness = Harness(monkeypatch, after=ENGLISH)
    monkeypatch.setattr(
        win32, "GetKeyboardLayoutList", lambda size, buffer: asked.append((size, buffer)) or 2
    )
    harness.switcher.switch(ARABIC)
    assert asked == [(0, None)]


def test_a_layout_handle_read_back_sign_extended_still_counts_as_the_target(monkeypatch):
    harness = Harness(monkeypatch, after=0xFFFFFFFFF0C00409)
    harness.switcher.switch(0xF0C00409)
    assert harness.lines == ["Switched the layout to F0C00409"]
    assert harness.sender.win_spaces == 0
