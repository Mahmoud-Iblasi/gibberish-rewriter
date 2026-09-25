r"""%APPDATA%\GibberishRewriter\config.json, created from the defaults and polled for changes.

Mirrors ``csharp/src/GibberishRewriter.App/ConfigFile.cs``.
"""

from __future__ import annotations

import os


class ConfigFile:
    """The config file and whether it changed since the last read."""

    POLL_INTERVAL_MS = 2000

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self._stamp: tuple[int, int] | None = None

    @staticmethod
    def app_data_folder() -> str:
        """C#'s ``Environment.SpecialFolder.ApplicationData``, which is %APPDATA% on Windows."""
        roaming = os.environ.get("APPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Roaming"
        )
        return os.path.join(roaming, "GibberishRewriter")

    @staticmethod
    def default_path() -> str:
        return os.path.join(ConfigFile.app_data_folder(), "config.json")

    def ensure_exists(self, default_text: str) -> None:
        """Writes the default config if there is no file yet."""
        if os.path.exists(self.file_path):
            return
        folder = os.path.dirname(self.file_path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8", newline="") as file:
            file.write(default_text)

    def read_if_changed(self) -> str | None:
        """The file's text on the first call and whenever it changed since, else None. A missing file, or one
        another app has locked, reads as unchanged, so the next poll tries again."""
        try:
            status = os.stat(self.file_path)
        except OSError:
            return None
        stamp = (status.st_mtime_ns, status.st_size)
        if stamp == self._stamp:
            return None
        try:
            text = ConfigFile.read_text(self.file_path)
        except OSError:
            return None
        self._stamp = stamp
        return text

    @staticmethod
    def read_text(path: str) -> str:
        """The file as UTF-8, without a byte order mark at the start.

        The Core's ConfigParser deliberately refuses a BOM, as ``JsonDocument`` does, so a file saved by Notepad
        only works because it is stripped here. Read as bytes and decoded, because "utf-8-sig" strips the mark and
        ``errors="replace"`` matches .NET's ``StreamReader``, which substitutes rather than throwing.
        """
        with open(path, "rb") as file:
            return file.read().decode("utf-8-sig", errors="replace")
