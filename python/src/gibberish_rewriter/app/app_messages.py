"""Texts of the app's notifications and its message box. The C# app uses the same texts.

Mirrors ``csharp/src/GibberishRewriter.App/AppMessages.cs``. The C# static class becomes module constants and
functions, as ``hkl.py`` does, so ``app_messages.started(...)`` reads beside ``AppMessages.Started(...)``.
"""

from __future__ import annotations

TITLE = "Gibberish Rewriter"

TOOLTIP = "Gibberish Rewriter (Python)"
"""The C# says "(C#)", so the tooltip alone tells you which app is in the tray."""

NEW_LINE = "\r\n"
"""C#'s ``Environment.NewLine``, so the message box reads the same in both apps."""

ALREADY_RUNNING = (
    "Gibberish Rewriter is already running (C# or Python version). Exit it from its tray icon first."
)

LAYOUTS_NOT_FOUND = (
    'Couldn\'t find exactly one Latin and one Arabic keyboard layout. Set "layouts" in the config file to HKL '
    'values such as "04090409" and "04012C01". Gibberish Rewriter stays disabled until then.'
)

LAYOUTS_SAME = (
    "layouts.latin and layouts.arabic are the same layout. Gibberish Rewriter stays disabled until they differ."
)


def layout_not_installed(hkl: str) -> str:
    return (
        f"The keyboard layout {hkl} in the config file isn't installed. "
        "Gibberish Rewriter stays disabled until it is."
    )


def layout_has_dead_keys(hkl: str) -> str:
    return (
        f"The keyboard layout {hkl} has dead keys, which Gibberish Rewriter doesn't support. "
        "Gibberish Rewriter stays disabled."
    )


def started(latin_hkl: str, arabic_hkl: str, fix_typed: str, fix_selection: str) -> str:
    """Shown on every successful start, so a start that produced no tray icon is obvious."""
    return (
        f"Gibberish Rewriter is running. Layouts {latin_hkl} and {arabic_hkl}. "
        f"{fix_typed} fixes what you just typed, {fix_selection} fixes the selected text."
    )


def shared_files_unreadable(shared_folder: str, detail: str) -> str:
    """The app can't start without its shared files, so it says which folder it looked in."""
    return (
        f"Gibberish Rewriter can't start: it couldn't read its files in{NEW_LINE}{shared_folder}"
        f"{NEW_LINE}{NEW_LINE}{detail}{NEW_LINE}{NEW_LINE}"
        'Copy the whole "shared" folder next to the program and start it again.'
    )


def config_invalid(code: str, message: str) -> str:
    return f"The config file has an error, so the last good settings stay in use. {code}: {message}"
