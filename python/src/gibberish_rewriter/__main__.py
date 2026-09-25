"""The entry point: ``python -m gibberish_rewriter`` and ``--dump-layouts <file>``.

Mirrors ``csharp/src/GibberishRewriter.App/Program.cs``. C#'s ``[STAThread]`` and ``Application.Run`` become the
tray's message loop, which AppHost.run enters; everything else is the same, in the same order.
"""

from __future__ import annotations

import ctypes
import os
import sys
import threading
from collections.abc import Sequence
from ctypes import wintypes
from pathlib import Path

from gibberish_rewriter.app import app_messages, dump_layouts_command, startup
from gibberish_rewriter.win import single_instance, win32
from gibberish_rewriter.app.app_host import AppHost
from gibberish_rewriter.app.app_log import AppLog
from gibberish_rewriter.app.config_file import ConfigFile

MB_OK = 0x0
MB_ICONERROR = 0x10
MB_ICONINFORMATION = 0x40

_MessageBox = win32.user32.MessageBoxW
_MessageBox.restype = ctypes.c_int
_MessageBox.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]


def shared_folder() -> str:
    """``shared/`` beside the program, which is C#'s ``AppContext.BaseDirectory``.

    Frozen, that is the executable's folder. From a source tree it is the repository's, three folders above this
    file.
    """
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve().parent / "shared")
    return str(Path(__file__).resolve().parents[3] / "shared")


def message_box(text: str, icon: int) -> None:
    _MessageBox(None, text, app_messages.TITLE, MB_OK | icon)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    shared = shared_folder()
    if len(args) == 2 and args[0] == "--dump-layouts":
        config_path = ConfigFile.default_path()
        config_text = ConfigFile.read_text(config_path) if os.path.exists(config_path) else None
        try:
            return dump_layouts_command.run(shared, config_text, args[1], sys.stderr)
        except Exception as exception:  # noqa: BLE001 - re-raised unless it is a shared file problem
            if not startup.is_shared_file_problem(exception):
                raise
            print(app_messages.shared_files_unreadable(shared, str(exception)), file=sys.stderr)
            return 2

    instance = single_instance.try_acquire()
    if instance is None:
        message_box(app_messages.ALREADY_RUNNING, MB_ICONINFORMATION)
        return 1
    with instance:
        log = AppLog(AppLog.default_path())
        _log_unhandled_errors(log)
        try:
            host = AppHost(shared, log)
        except Exception as exception:  # noqa: BLE001 - re-raised unless it is a shared file problem
            if not startup.is_shared_file_problem(exception):
                raise
            # Without shared/ there is no tray icon to notify from, so this is the one message box.
            log.write(f"Can't read the shared files: {type(exception).__name__}")
            message_box(app_messages.shared_files_unreadable(shared, str(exception)), MB_ICONERROR)
            return 2
        with host:
            host.exit_requested = host.stop
            host.run()
    return 0


def _log_unhandled_errors(log: AppLog) -> None:
    """C#'s AppDomain.UnhandledException and Application.ThreadException, which Python splits the same way: one
    hook for the thread that runs the message loop and one for every other thread."""
    main_hook = sys.excepthook
    thread_hook = threading.excepthook

    def on_main(kind, value, traceback):  # noqa: ANN001, ANN202 - sys.excepthook's own signature
        log.write(f"Crash: {kind.__name__}")
        main_hook(kind, value, traceback)

    def on_thread(args):  # noqa: ANN001, ANN202 - threading.ExceptHookArgs is a private type
        log.write(f"UI error: {args.exc_type.__name__}")
        thread_hook(args)

    sys.excepthook = on_main
    threading.excepthook = on_thread


if __name__ == "__main__":
    sys.exit(main())
