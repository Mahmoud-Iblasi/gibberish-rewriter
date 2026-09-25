r"""The GibberishRewriter value under HKCU\Software\Microsoft\Windows\CurrentVersion\Run.

Mirrors ``csharp/src/GibberishRewriter.App/Win/Autostart.cs``, through ``winreg`` rather than ``Microsoft.Win32``.
The C# writes its exe path alone; the Python app writes ``"<venv>\Scripts\pythonw.exe" -m gibberish_rewriter``,
so everything here takes an argument string beside the exe path. Both apps use the same value name, so only one
version starts with Windows.
"""

from __future__ import annotations

import os
import sys
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "GibberishRewriter"
MODULE = "gibberish_rewriter"
"""The installed package name, which ``pythonw.exe -m`` starts."""


class Autostart:
    """The registry value, read and written for one command."""

    def __init__(self, exe_path: str, arguments: str = "") -> None:
        self._exe_path = exe_path
        self._arguments = arguments

    @staticmethod
    def command_for(exe_path: str, arguments: str = "") -> str:
        """The command line to store: the exe always quoted, the arguments after it."""
        quoted = f'"{exe_path}"'
        return f"{quoted} {arguments}" if arguments else quoted

    @staticmethod
    def split(command: str) -> tuple[str, str]:
        """A stored command as (exe, arguments). A quoted exe ends at its closing quote; an unquoted one is the
        whole command, because C# compares the whole trimmed value and exe paths contain spaces."""
        text = command.strip()
        if text.startswith('"'):
            end = text.find('"', 1)
            if end >= 0:
                return text[1:end], text[end + 1 :].strip()
        return text.strip('"'), ""

    @staticmethod
    def points_at(command: str | None, exe_path: str, arguments: str = "") -> bool:
        """True when ``command`` runs exactly this exe with these arguments, quoted or not, in any letter case.

        The path is compared case-insensitively, as C# does with ``StringComparison.OrdinalIgnoreCase``; the
        arguments are not, because a Python module name is case-sensitive.
        """
        if command is None:
            return False
        exe, rest = Autostart.split(command)
        return exe.casefold() == exe_path.casefold() and rest == arguments.strip()

    @property
    def command(self) -> str:
        return Autostart.command_for(self._exe_path, self._arguments)

    @property
    def is_enabled(self) -> bool:
        """True when the registry value starts this app."""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                value, _kind = winreg.QueryValueEx(key, VALUE_NAME)
        except OSError:
            return False
        return Autostart.points_at(value if isinstance(value, str) else None, self._exe_path, self._arguments)

    def enable(self) -> None:
        """Writes this app's command, replacing a value the C# app wrote."""
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, self.command)

    def disable(self) -> None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            # C# passes throwOnMissingValue: false and skips a missing key with ?., so neither is an error.
            pass


def for_this_app() -> Autostart:
    """Pythonw.exe beside the running interpreter, starting the package with no console window."""
    windowless = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = windowless if os.path.exists(windowless) else sys.executable
    return Autostart(exe, f"-m {MODULE}")
