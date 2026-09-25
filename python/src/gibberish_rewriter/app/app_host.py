"""Starts everything, reloads the config, and answers the tray.

Mirrors ``csharp/src/GibberishRewriter.App/AppHost.cs``. Where the C# runs everything here on the WinForms UI
thread, this runs on the thread that calls ``run`` (pystray's message loop) plus one background thread that polls
the config file, so every method that touches the slot or the config takes ``_lock``.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

from gibberish_rewriter.core.chord_detector import ChordAction
from gibberish_rewriter.core.config import AppConfig, ConfigParser
from gibberish_rewriter.core.engine import Engine
from gibberish_rewriter.core.key_names import KeyNames
from gibberish_rewriter.core.text_converter import TextConverter
from gibberish_rewriter.core.word_list import WordList

from gibberish_rewriter.app import app_messages
from gibberish_rewriter.win import autostart, foreground, hkl, layout_pair_resolver, layout_reader, start_notice, win32
from gibberish_rewriter.win.action_worker import ActionWorker, caps_lock_is_on
from gibberish_rewriter.app.app_log import AppLog
from gibberish_rewriter.win.clipboard_owner_window import ClipboardOwnerWindow
from gibberish_rewriter.win.clipboard_service import ClipboardService
from gibberish_rewriter.app.config_file import ConfigFile
from gibberish_rewriter.win.engine_slot import EngineSlot
from gibberish_rewriter.win.hkl import LayoutPair
from gibberish_rewriter.win.hook_thread import HookThread
from gibberish_rewriter.win.hook_watchdog import HookActivity, HookWatchdog
from gibberish_rewriter.win.input_sender import InputSender
from gibberish_rewriter.win.key_state import KeyStateTracker
from gibberish_rewriter.win.keyboard_hook import KeyboardHook
from gibberish_rewriter.win.layout_reader import DeadKeyError
from gibberish_rewriter.win.layout_switcher import LayoutSwitcher
from gibberish_rewriter.win.mouse_hook import MouseHook
from gibberish_rewriter.app.tray import Tray
from gibberish_rewriter.win.windows_platform import WindowsPlatform


def _sleep_ms(milliseconds: int) -> None:
    time.sleep(milliseconds / 1000)


class AppHost:
    """Starts everything, reloads the config, and answers the tray."""

    def __init__(self, shared_folder: str, log: AppLog) -> None:
        # Reading shared/ is the first thing it does, so a file it cannot read stops the start here.
        self._log = log
        self._names = KeyNames.load(os.path.join(shared_folder, "keys.json"))
        self._words = WordList.load(os.path.join(shared_folder, "wordlists", "english.txt"))
        default_text = Path(os.path.join(shared_folder, "config.default.json")).read_text(encoding="utf-8")
        self._parser = ConfigParser(self._names, default_text)
        self._config: AppConfig = self._parser.defaults
        self._config_file = ConfigFile(ConfigFile.default_path())
        self._config_file.ensure_exists(default_text)
        self._autostart = autostart.for_this_app()
        self._tray = Tray(os.path.join(shared_folder, "icons"))

        self._lock = threading.RLock()
        self._stopping = threading.Event()
        self._slot: EngineSlot | None = None
        self._pair_error: str | None = None
        self._loaded = False
        self._watchdog: HookWatchdog | None = None
        self._config_poll: threading.Thread | None = None
        self.exit_requested: Callable[[], None] | None = None

        self._clipboard_owner = ClipboardOwnerWindow(self._on_session_unlock)
        self._keys = KeyStateTracker()
        self._activity = HookActivity()
        self._sender = InputSender(log.write)
        self._clipboard = ClipboardService(lambda: self._clipboard_owner.handle, log.write, _sleep_ms)
        self._switcher = LayoutSwitcher(self._sender, log.write, _sleep_ms)
        self._worker = ActionWorker(log.write)
        self._hooks = HookThread(
            KeyboardHook(lambda: self._slot, self._sender, self._keys, self._activity, log.write),
            MouseHook(lambda: self._slot, self._activity, log.write),
            self._activity,
            self._on_hooks_reinstalled,
            log.write,
        )

        self._tray.enabled_clicked = self._on_enabled_clicked
        self._tray.open_config_clicked = self._on_open_config_clicked
        self._tray.autostart_clicked = self._on_autostart_clicked
        self._tray.exit_clicked = self._on_exit_clicked

    def run(self) -> None:
        """Shows the tray icon and runs the message loop until the tray is stopped.

        ``start`` runs once the icon is on screen, because a notification sent before that is dropped. The C#
        calls Start() first and then Application.Run(), which it can because a NotifyIcon is visible at once.
        """
        self._tray.run(self._start_safely)

    def stop(self) -> None:
        """Any thread. Ends run()."""
        self._tray.stop()

    def start(self) -> None:
        self._log.write("Starting")
        self._load(self._config_file.read_if_changed())
        self._hooks.start()
        self._watchdog = HookWatchdog(
            self._activity,
            lambda: foreground.is_blocked_by_elevation(win32.GetForegroundWindow()),
            self._hooks.reinstall,
            self._log.write,
            lambda: foreground.class_name_of(win32.GetForegroundWindow()),
        )
        self._config_poll = threading.Thread(target=self._poll_config, name="ConfigPoll", daemon=True)
        self._config_poll.start()
        with self._lock:
            slot = self._slot
            config = self._config
        if slot is not None:
            # A start with no notification and no tray icon is the failure this makes visible.
            message = app_messages.started(
                hkl.format(slot.pair.latin),
                hkl.format(slot.pair.arabic),
                config.fix_typed.format(self._names),
                config.fix_selection.format(self._names),
            )
            threading.Thread(
                target=self._show_start_notice, args=(message,), name="StartNotice", daemon=True
            ).start()

    def _show_start_notice(self, message: str) -> None:
        """C# polls with a WinForms timer on the UI thread; tray.notify may be called from any thread."""
        waited = 0
        while not start_notice.should_show(
            start_notice.taskbar_exists(), start_notice.notification_state(), waited
        ):
            if self._stopping.wait(start_notice.POLL_INTERVAL_MS / 1000):
                return
            waited += start_notice.POLL_INTERVAL_MS
        self._tray.notify(message)
        self._log.write(
            "Showed the start notification" if waited == 0 else f"Showed the start notification after {waited} ms"
        )

    def close(self) -> None:
        self._stopping.set()
        if self._config_poll is not None:
            self._config_poll.join(2.0)
        if self._watchdog is not None:
            self._watchdog.close()
        self._hooks.close()
        self._set_slot(None)
        self._worker.close()
        self._tray.close()
        self._clipboard_owner.close()
        self._log.write("Exited")

    def __enter__(self) -> AppHost:
        return self

    def __exit__(self, *exception: object) -> None:
        self.close()

    def _start_safely(self) -> None:
        """pystray runs the setup callback on its own thread, where an escaping error would be swallowed."""
        try:
            self.start()
        except Exception as exception:  # noqa: BLE001 - logged first, so a failed start is never silent
            self._log.write(f"Start failed: {type(exception).__name__}")
            raise

    def _poll_config(self) -> None:
        """The file is checked for changes every 2 seconds. C# uses a WinForms timer on the UI thread."""
        while not self._stopping.wait(ConfigFile.POLL_INTERVAL_MS / 1000):
            try:
                self._load(self._config_file.read_if_changed())
            except Exception as exception:  # noqa: BLE001 - a reload must never end the poll thread
                self._log.write(f"Config reload error: {type(exception).__name__}")

    def _load(self, text: str | None) -> None:
        """Applies config text (None: unchanged) and resolves the layout pair. An invalid file keeps
        the last good config; at startup that is the defaults."""
        with self._lock:
            if text is None and self._loaded:
                return
            if text is not None:
                result = self._parser.parse(text)
                if result.error is not None:
                    self._log.write(f"Config error {result.error.code}")
                    self._tray.notify(app_messages.config_invalid(result.error.code, result.error.message))
                    if self._loaded:
                        return
                else:
                    assert result.config is not None, "parse returns a config whenever it returns no error."
                    self._config = result.config
                    self._log.write("Config loaded")
            self._loaded = True

            resolution = layout_pair_resolver.resolve(
                self._config.latin_layout, self._config.arabic_layout, layout_reader.installed_with_key_a()
            )
            pair = resolution.pair
            current = self._slot
            if pair is None:
                assert resolution.error is not None, "resolve returns an error whenever it returns no pair."
                self._disable(resolution.error)
            elif current is not None and current.pair == pair:
                current.engine.apply_config(self._config)
            else:
                try:
                    self._set_slot(self._build_slot(pair))
                    self._pair_error = None
                    self._log.write(f"Layout pair {hkl.format(pair.latin)} and {hkl.format(pair.arabic)}")
                except DeadKeyError as exception:
                    self._disable(app_messages.layout_has_dead_keys(hkl.format(exception.layout)))
            self._update_tray()

    def _build_slot(self, pair: LayoutPair) -> EngineSlot:
        table = layout_reader.read_table(self._names, pair)
        platform = WindowsPlatform(
            pair, self._sender, self._clipboard, self._switcher, self._keys, self._notify_from_any_thread
        )
        engine: Engine | None = None

        def start_action(action: ChordAction) -> None:
            assert engine is not None, "start_action only runs once the Engine exists."
            self._worker.enqueue(engine, action)

        engine = Engine(
            self._names,
            table,
            TextConverter(table, self._words),
            self._config,
            platform,
            start_action,
            caps_lock_is_on(),
        )
        return EngineSlot(engine, pair)

    def _set_slot(self, slot: EngineSlot | None) -> None:
        """Swaps the Engine the hooks feed. The old one is disabled, which clears its run."""
        old = self._slot
        self._slot = slot
        if old is not None:
            old.engine.enabled = False

    def _disable(self, error: str) -> None:
        self._set_slot(None)
        self._pair_error = error
        self._log.write("No usable layout pair; disabled")
        self._tray.notify(error)

    def _update_tray(self) -> None:
        slot = self._slot
        self._tray.show(slot.engine.enabled if slot is not None else False, self._autostart.is_enabled)

    def _notify_from_any_thread(self, message: str) -> None:
        self._log.write(f"Notification: {message}")
        self._tray.notify(message)

    def _on_enabled_clicked(self) -> None:
        with self._lock:
            slot = self._slot
            if slot is None:
                if self._pair_error is not None:
                    self._tray.notify(self._pair_error)
                return
            slot.engine.enabled = not slot.engine.enabled
            self._log.write("Enabled from the tray" if slot.engine.enabled else "Disabled from the tray")
            self._update_tray()

    def _on_open_config_clicked(self) -> None:
        os.startfile(self._config_file.file_path)  # noqa: S606 - C# opens it with ShellExecute for the same reason

    def _on_autostart_clicked(self) -> None:
        with self._lock:
            try:
                if self._autostart.is_enabled:
                    self._autostart.disable()
                else:
                    self._autostart.enable()
            except OSError as exception:
                # winreg raises OSError for a denied or missing key, which is what the C# catches three types for.
                self._log.write(f"Start with Windows failed: {type(exception).__name__}")
            self._update_tray()

    def _on_exit_clicked(self) -> None:
        if self.exit_requested is not None:
            self.exit_requested()

    def _on_hooks_reinstalled(self) -> None:
        """Hook thread. The hooks may have missed key events while they were gone."""
        self._keys.clear()
        slot = self._slot
        if slot is not None:
            slot.engine.reset_after_missed_input(caps_lock_is_on())

    def _on_session_unlock(self) -> None:
        """The message loop's thread, from WM_WTSSESSION_CHANGE (C#: SystemEvents.SessionSwitch)."""
        self._keys.clear()
        slot = self._slot
        if slot is not None:
            slot.engine.reset_after_missed_input(caps_lock_is_on())
        self._log.write("Session unlocked")
