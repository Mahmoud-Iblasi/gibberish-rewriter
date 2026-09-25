"""Mirrors csharp/tests/GibberishRewriter.App.Tests/AutostartTests.cs, plus the arguments the Python command needs.
Nothing here writes to the registry: the value under Run would start this app at every logon."""

from __future__ import annotations

import uuid

import pytest

from gibberish_rewriter.win import autostart, single_instance
from gibberish_rewriter.win.autostart import Autostart

EXE = r"C:\Users\me\gibberish rewriter\GibberishRewriter.exe"
PYTHONW = r"C:\Users\me\gibberish rewriter\python\.venv\Scripts\pythonw.exe"
MODULE_ARGUMENTS = "-m gibberish_rewriter"


def test_command_for_quotes_the_path():
    assert Autostart.command_for(EXE) == f'"{EXE}"'


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (r'"C:\Users\me\gibberish rewriter\GibberishRewriter.exe"', True),
        (r"C:\USERS\ME\gibberish rewriter\GibberishRewriter.exe", True),
        (r'"C:\Users\me\gibberish rewriter\python\.venv\Scripts\pythonw.exe" -m gibberish_rewriter', False),
        (None, False),
    ],
)
def test_points_at_recognizes_only_this_exe(command, expected):
    assert Autostart.points_at(command, EXE) is expected


def test_the_python_command_names_the_interpreter_and_the_module():
    """The Python app writes "<venv>\\Scripts\\pythonw.exe" -m gibberish_rewriter."""
    assert Autostart.command_for(PYTHONW, MODULE_ARGUMENTS) == f'"{PYTHONW}" {MODULE_ARGUMENTS}'


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (f'"{PYTHONW}" -m gibberish_rewriter', True),
        (f'"{PYTHONW.upper()}" -m gibberish_rewriter', True),
        (f'"{PYTHONW}"', False),
        (f'"{PYTHONW}" -m something_else', False),
        (f'"{EXE}"', False),
    ],
)
def test_points_at_compares_the_arguments_too(command, expected):
    assert Autostart.points_at(command, PYTHONW, MODULE_ARGUMENTS) is expected


def test_for_this_app_starts_this_interpreter_with_no_console():
    entry = autostart.for_this_app()
    assert entry.command.endswith('" -m gibberish_rewriter')
    assert "python" in entry.command.lower()
    assert Autostart.points_at(entry.command, *Autostart.split(entry.command)) is True


def test_both_apps_use_the_same_value_under_run():
    """The same value name, so only one version starts with Windows."""
    assert autostart.RUN_KEY == r"Software\Microsoft\Windows\CurrentVersion\Run"
    assert autostart.VALUE_NAME == "GibberishRewriter"


def test_is_enabled_is_false_when_the_value_belongs_to_another_command():
    """The registry is only read here. A value written by the C# app, or none at all, is not this app."""
    assert Autostart(r"C:\nowhere\gibberish-rewriter-not-installed.exe", "-m nothing").is_enabled is False


def test_both_apps_use_the_same_mutex_name():
    assert single_instance.MUTEX_NAME == r"Local\GibberishRewriter.SingleInstance"


def test_a_second_copy_is_refused_until_the_first_exits():
    name = r"Local\GibberishRewriter.Test." + uuid.uuid4().hex
    first = single_instance.try_acquire(name)
    assert first is not None
    try:
        assert single_instance.try_acquire(name) is None
    finally:
        first.close()
    again = single_instance.try_acquire(name)
    assert again is not None
    again.close()
