"""Mirrors csharp/tests/GibberishRewriter.App.Tests/StartupTests.cs: the start notification, and a shared file
that can't be read. The C# lists exception types; the Python ones are different types for the same
three situations, so both the file problems and the app's own bugs are listed here."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import shared_files
from gibberish_rewriter.core.config import ConfigParser
from gibberish_rewriter.core.key_names import KeyNames

from gibberish_rewriter.app import app_messages, startup
from gibberish_rewriter.app.tray import MAX_NOTIFICATION_LENGTH, Tray

NAMES = KeyNames.load(shared_files.path_of("keys.json"))


def started_text() -> str:
    config = ConfigParser(NAMES, shared_files.read_text("config.default.json")).defaults
    return app_messages.started(
        "04090409", "04012C01", config.fix_typed.format(NAMES), config.fix_selection.format(NAMES)
    )


def test_the_start_notification_names_both_layouts():
    text = started_text()
    assert "04090409" in text
    assert "04012C01" in text


def test_the_start_notification_names_both_hotkeys_as_the_config_spells_them():
    text = started_text()
    assert "Shift+CapsLock+Tab" in text
    assert "Shift+CapsLock+Backquote" in text


def test_the_start_notification_fits_in_a_balloon():
    """A balloon tip is cut off past 255 characters (Tray.MAX_NOTIFICATION_LENGTH)."""
    assert len(started_text()) <= MAX_NOTIFICATION_LENGTH == 255


def test_the_tooltip_says_which_app_is_in_the_tray():
    """The C# says "(C#)", so a tray icon is never ambiguous."""
    assert app_messages.TOOLTIP == "Gibberish Rewriter (Python)"


def test_the_unreadable_message_names_the_folder_and_the_error():
    text = app_messages.shared_files_unreadable(r"C:\dist\shared", "Could not find a part of the path.")
    assert r"C:\dist\shared" in text
    assert "Could not find a part of the path." in text
    assert "shared" in text


@pytest.mark.parametrize(
    "exception",
    [
        FileNotFoundError(2, "No such file or directory"),
        NotADirectoryError(20, "Not a directory"),
        PermissionError(13, "Permission denied"),
        OSError(1, "Some other file error"),
        ValueError("tableKeys lists unknown key KeyQ"),
        KeyError("Shift"),
        json.JSONDecodeError("Expecting value", "", 0),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
    ],
)
def test_a_shared_file_problem_is_recognized(exception):
    assert startup.is_shared_file_problem(exception) is True


@pytest.mark.parametrize(
    "exception",
    [RuntimeError("a bug"), TypeError("a bug"), IndexError("a bug"), AttributeError("a bug")],
)
def test_a_bug_in_the_app_is_not_treated_as_a_shared_file_problem(exception):
    assert startup.is_shared_file_problem(exception) is False


def test_a_missing_shared_folder_raises_something_the_guard_catches(tmp_path):
    """The real failure: the published folder was missing shared\\icons, and the app exited silently."""
    with pytest.raises(Exception) as caught:  # noqa: PT011 - the point is which type it turns out to be
        KeyNames.load(tmp_path / "gibberish-rewriter-no-such-folder" / "keys.json")
    assert startup.is_shared_file_problem(caught.value) is True


def test_a_missing_icons_folder_raises_something_the_guard_catches(tmp_path):
    """The icons are shared files too, and the Tray is what reads them."""
    with pytest.raises(Exception) as caught:  # noqa: PT011
        Tray(str(tmp_path / "no-such-icons"))
    assert startup.is_shared_file_problem(caught.value) is True


def test_a_file_that_is_not_an_icon_raises_something_the_guard_catches(tmp_path):
    """C#'s Icon constructor raises ArgumentException here; Pillow raises UnidentifiedImageError."""
    icons = tmp_path / "icons"
    icons.mkdir()
    (icons / "tray.ico").write_bytes(b"this is not an icon")
    (icons / "tray-disabled.ico").write_bytes(b"this is not an icon either")
    with pytest.raises(Exception) as caught:  # noqa: PT011
        Tray(str(icons))
    assert startup.is_shared_file_problem(caught.value) is True


def test_the_real_icons_load():
    """The published folder that started all this was missing exactly these two files."""
    for name in ("tray.ico", "tray-disabled.ico"):
        assert Path(shared_files.path_of("icons/" + name)).is_file()
    Tray(str(shared_files.path_of("icons")))
