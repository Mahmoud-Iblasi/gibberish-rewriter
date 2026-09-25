"""The tray icon, its menu and notifications.

Mirrors ``csharp/src/GibberishRewriter.App/Tray.cs``, with ``pystray`` and Pillow where the C# has a WinForms
``NotifyIcon``. The menu, its order, the tooltip and the notifications are the same; only the toolkit
differs. ``run`` must be called on the thread that owns the app's message loop, and the icon is not on screen — so
``notify`` does nothing — until it has started, which is why ``run`` takes the callback that starts everything.
"""

from __future__ import annotations

import os
from collections.abc import Callable

import pystray
from PIL import Image

from gibberish_rewriter.app import app_messages

MAX_NOTIFICATION_LENGTH = 255
"""A balloon tip is cut off past this, so the text is cut here instead, as the C# does."""

NOTIFICATION_TIMEOUT_MS = 5000
"""What the C# passes to ShowBalloonTip. Windows has ignored the value since Vista; pystray doesn't take one."""


class Tray:
    """The tray icon and its menu. Every method but notify runs on the thread that called run."""

    def __init__(self, icons_folder: str) -> None:
        self._enabled_icon = _load_icon(os.path.join(icons_folder, "tray.ico"))
        self._disabled_icon = _load_icon(os.path.join(icons_folder, "tray-disabled.ico"))
        self._enabled = False
        self._autostart = False
        self.enabled_clicked: Callable[[], None] | None = None
        self.open_config_clicked: Callable[[], None] | None = None
        self.autostart_clicked: Callable[[], None] | None = None
        self.exit_clicked: Callable[[], None] | None = None
        menu = pystray.Menu(
            pystray.MenuItem("Enabled", self._on_enabled, checked=lambda _item: self._enabled),
            pystray.MenuItem("Open config file", self._on_open_config),
            pystray.MenuItem(
                "Start with Windows", self._on_autostart, checked=lambda _item: self._autostart
            ),
            pystray.MenuItem("Exit", self._on_exit),
        )
        self._icon = pystray.Icon(
            "GibberishRewriter", icon=self._disabled_icon, title=app_messages.TOOLTIP, menu=menu
        )

    def run(self, started: Callable[[], None]) -> None:
        """Shows the icon and runs the message loop until stop(). ``started`` runs once the icon is on screen."""
        self._icon.run(setup=lambda icon: _start(icon, started))

    def stop(self) -> None:
        """Any thread. Ends run()."""
        self._icon.stop()

    def show(self, enabled: bool, autostart: bool) -> None:
        self._enabled = enabled
        self._autostart = autostart
        self._icon.icon = self._enabled_icon if enabled else self._disabled_icon
        self._icon.update_menu()

    def notify(self, message: str) -> None:
        """Any thread. Shell_NotifyIcon may be called from any thread, so no marshalling is needed."""
        if len(message) > MAX_NOTIFICATION_LENGTH:
            message = message[: MAX_NOTIFICATION_LENGTH - 3] + "..."
        self._icon.notify(message, app_messages.TITLE)

    def close(self) -> None:
        self._icon.visible = False

    def __enter__(self) -> Tray:
        return self

    def __exit__(self, *exception: object) -> None:
        self.close()

    def _on_enabled(self, _icon: object, _item: object) -> None:
        _raise_event(self.enabled_clicked)

    def _on_open_config(self, _icon: object, _item: object) -> None:
        _raise_event(self.open_config_clicked)

    def _on_autostart(self, _icon: object, _item: object) -> None:
        _raise_event(self.autostart_clicked)

    def _on_exit(self, _icon: object, _item: object) -> None:
        _raise_event(self.exit_clicked)


def _start(icon: pystray.Icon, started: Callable[[], None]) -> None:
    """pystray's setup callback. A custom one has to make the icon visible itself."""
    icon.visible = True
    started()


def _load_icon(path: str) -> Image.Image:
    """Reads a .ico into memory. A missing file or one that is not an icon raises an OSError, which Startup
    recognizes as a shared file problem."""
    with Image.open(path) as image:
        return image.convert("RGBA")


def _raise_event(handler: Callable[[], None] | None) -> None:
    if handler is not None:
        handler()
