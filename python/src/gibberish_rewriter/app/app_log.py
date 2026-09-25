r"""%APPDATA%\GibberishRewriter\logs\python.log, rolled over to python.log.1 at 1 MB.

Callers log event kinds, counts, window class names and errors only, never typed text.
Mirrors ``csharp/src/GibberishRewriter.App/AppLog.cs``.
"""

from __future__ import annotations

import datetime
import os
import threading

from gibberish_rewriter.app.config_file import ConfigFile


class AppLog:
    """One log file, written from any thread."""

    DEFAULT_MAX_BYTES = 1024 * 1024

    def __init__(self, file_path: str, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        self.file_path = file_path
        self._max_bytes = max_bytes
        self._lock = threading.Lock()

    @staticmethod
    def default_path() -> str:
        return os.path.join(ConfigFile.app_data_folder(), "logs", "python.log")

    def write(self, message: str) -> None:
        """Any thread. Never raises: a log that can't be written is skipped."""
        now = datetime.datetime.now()
        # C# formats with "yyyy-MM-dd HH:mm:ss.fff"; %f is microseconds, so the milliseconds are cut here.
        line = f"{now:%Y-%m-%d %H:%M:%S}.{now.microsecond // 1000:03d} {message}\n"
        with self._lock:
            try:
                folder = os.path.dirname(self.file_path)
                if folder:
                    os.makedirs(folder, exist_ok=True)
                if (
                    os.path.exists(self.file_path)
                    and os.path.getsize(self.file_path) + len(line.encode("utf-8")) > self._max_bytes
                ):
                    os.replace(self.file_path, self.file_path + ".1")
                # newline="" keeps the "\n" the C# writes; Python would otherwise turn it into "\r\n".
                with open(self.file_path, "a", encoding="utf-8", newline="") as file:
                    file.write(line)
            except OSError:
                pass
