"""Joins the Core modules: decides pass or swallow, records the run, and runs actions."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

from .chord_detector import ChordAction, ChordDecision, ChordDetector
from .config import AppConfig, Chord
from .key_names import VK_BACKSPACE, VK_CAPS_LOCK, VK_MASK, HoldKeys, KeyNames
from .key_table import KeyTable, LayoutKind, state_of
from .platform import (
    ADMINISTRATOR_WINDOW,
    CLIPBOARD_BUSY,
    ClipboardUnavailableError,
    ForegroundWindow,
    Platform,
    Shortcut,
)
from .text_converter import Conversion, TextConverter
from .typing_run import KeyRecord, TypingRun

_CLIPBOARD_POLL_MS = 20


@dataclass(frozen=True)
class KeyEvent:
    """One low-level key event."""

    vk: int
    down: bool
    injected_by_self: bool
    is_packet: bool
    modifiers: HoldKeys
    """Shift, Ctrl, Alt and Win as Windows reports them just before this event."""
    window: int
    layout: LayoutKind | None
    """The foreground layout, or None when it isn't one of the pair."""


@dataclass(frozen=True)
class KeyDecision:
    """Whether to swallow a key event, and keys to press right away."""

    swallow: bool
    send_keys: tuple[int, ...] = ()


PASS = KeyDecision(False, ())
"""Let the event through and send nothing."""


@dataclass(frozen=True)
class _SelectionFix:
    """The last selection fix that pasted. source_layout is the layout of the text before it."""

    window: int
    source_layout: LayoutKind


class Engine:
    """Joins the Core modules: decides pass or swallow, records the run, and runs actions through Platform."""

    def __init__(
        self,
        names: KeyNames,
        table: KeyTable,
        converter: TextConverter,
        config: AppConfig,
        platform: Platform,
        start_action: Callable[[ChordAction], None],
        caps_lock_on: bool,
    ) -> None:
        """start_action is called outside the lock when a chord fires; the host calls run_action exactly once for
        each call, on its one worker thread. caps_lock_on is the Caps Lock toggle as Windows reports it at startup."""
        self._lock = threading.RLock()
        self._names = names
        self._table = table
        self._converter = converter
        self._platform = platform
        self._start_action = start_action
        self._config = config
        self._enabled = config.enabled
        self._caps_lock_on = caps_lock_on
        self._caps_lock_down_while_disabled = False
        self._busy = False
        self._break_during_action = False
        self._last_selection_fix: _SelectionFix | None = None
        self._chords = ChordDetector(names, config.fix_typed, config.fix_selection)
        self._run = TypingRun(config.max_run_length)

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        with self._lock:
            if value == self._enabled:
                return
            self._enabled = value
            self._caps_lock_down_while_disabled = False
            self._chords.set_chords(self._config.fix_typed, self._config.fix_selection)
            self._break()

    def apply_config(self, config: AppConfig) -> None:
        """A reloaded config. A chord being pressed is forgotten only when a hotkey changed."""
        with self._lock:
            if config.fix_typed != self._config.fix_typed or config.fix_selection != self._config.fix_selection:
                self._chords.set_chords(config.fix_typed, config.fix_selection)
            self._config = config
            self._run.max_length = config.max_run_length
        self.enabled = config.enabled

    def on_key(self, event: KeyEvent) -> KeyDecision:
        """Hook thread. Decides one key event."""
        with self._lock:
            decision, start = self._decide(event)
        if start is not None:
            self._start_action(start)
        return decision

    def on_mouse_down(self) -> None:
        """Hook thread. Any mouse button press is a break."""
        with self._lock:
            if self._enabled:
                self._break()

    def set_caps_lock_on(self, caps_lock_on: bool) -> None:
        """Any thread. Corrects the tracked Caps Lock toggle when Windows may have changed it without the hook
        seeing a key (after the lock screen or a UAC prompt, or after a hook was reinstalled)."""
        with self._lock:
            self._caps_lock_on = caps_lock_on

    def reset_after_missed_input(self, caps_lock_on: bool) -> None:
        """Any thread. After a hook reinstall or a session unlock, when the hooks may have missed key events:
        takes the Caps Lock toggle Windows reports, forgets a half-pressed chord, and breaks the run."""
        with self._lock:
            self._caps_lock_on = caps_lock_on
            self._caps_lock_down_while_disabled = False
            self._chords.set_chords(self._config.fix_typed, self._config.fix_selection)
            self._break()

    def run_action(self, action: ChordAction) -> None:
        """Worker thread. Runs the action start_action asked for. Platform errors other than
        ClipboardUnavailableError propagate; the host logs them."""
        try:
            with self._lock:
                config = self._config
            chord = config.fix_typed if action is ChordAction.FIX_TYPED else config.fix_selection
            if not self._platform.wait_for_release(self._release_keys(chord), config.release_timeout_ms):
                return
            with self._lock:
                # A key or click while the chord keys were still held has already reached the app, so the run
                # and any selection no longer match the screen: cancel. _end_action's deferred break clears both.
                if self._break_during_action:
                    return
            if action is ChordAction.FIX_TYPED:
                self._fix_typed(config)
                return
            try:
                self._fix_selection(config)
            finally:
                with self._lock:
                    self._run.clear()
        finally:
            self._end_action()

    def _decide(self, event: KeyEvent) -> tuple[KeyDecision, ChordAction | None]:
        if event.injected_by_self:
            return PASS, None
        if not self._enabled:
            self._track_caps_lock_while_disabled(event)
            return PASS, None
        if event.is_packet:
            if event.down:
                self._break()
            return PASS, None

        chord: ChordDecision = self._chords.on_key(event.vk, event.down, event.modifiers)
        if chord.caps_lock_toggled:
            self._caps_lock_on = not self._caps_lock_on
        start: ChordAction | None = None
        if chord.fired is not None and not self._busy:
            self._busy = True
            start = chord.fired
        if chord.swallow:
            send: list[int] = []
            if chord.replay_caps_lock:
                send.append(VK_CAPS_LOCK)
            if chord.send_mask_key:
                send.append(VK_MASK)
            return KeyDecision(True, tuple(send)), start
        if event.down:
            self._on_passed_key_down(event)
        return PASS, start

    def _on_passed_key_down(self, event: KeyEvent) -> None:
        """Records the key or breaks the run, for a key-down that reaches Windows."""
        if self._names.is_modifier(event.vk):
            return
        if event.modifiers & (HoldKeys.CTRL | HoldKeys.ALT | HoldKeys.WIN) or self._busy:
            self._break()
            return
        if event.vk == VK_BACKSPACE:
            self._last_selection_fix = None
            self._run.backspace(self._table)
            return
        layout = event.layout
        if layout is None:
            self._break()
            return

        shift = bool(event.modifiers & HoldKeys.SHIFT)
        state = state_of(shift, self._caps_lock_on)
        text = self._table.text_of(event.vk, layout, state)
        if len(text) == 0:
            self._break()
            return
        other = self._table.text_of(event.vk, layout.other(), state)
        self._last_selection_fix = None
        self._run.record(
            event.window,
            layout,
            KeyRecord(event.vk, shift, self._caps_lock_on, text, other if len(other) > 0 else text),
        )

    def _track_caps_lock_while_disabled(self, event: KeyEvent) -> None:
        if event.vk != VK_CAPS_LOCK:
            return
        if event.down and not self._caps_lock_down_while_disabled:
            self._caps_lock_on = not self._caps_lock_on
        self._caps_lock_down_while_disabled = event.down

    def _break(self) -> None:
        """Clears the run and forgets the last selection fix, or marks both for when the running action ends."""
        if self._busy:
            self._break_during_action = True
            return
        self._run.clear()
        self._last_selection_fix = None

    def _release_keys(self, chord: Chord) -> list[int]:
        return [*self._names.vks_of(chord.hold), chord.trigger_vk]

    def _end_action(self) -> None:
        with self._lock:
            self._busy = False
            if self._break_during_action:
                self._break_during_action = False
                self._break()

    def _fix_typed(self, config: AppConfig) -> None:
        """Fixes what was just typed. Also the undo, because the fix leaves the run describing the fixed text."""
        with self._lock:
            self._last_selection_fix = None

        foreground = self._platform.foreground_info()
        if foreground.is_blocked_by_elevation:
            self._platform.notify(ADMINISTRATOR_WINDOW)
            return

        with self._lock:
            if self._run.is_empty or foreground.window != self._run.window:
                self._run.clear()
                return
            text = self._run.text
            other_text = self._run.other_text
            target = self._run.layout.other()

        # One backspace per UTF-16 code unit, as Windows counts them and as the C# string length does: a
        # character outside the basic plane takes two.
        self._platform.send_backspaces(len(text.encode("utf-16-le")) // 2)
        self._platform.type_text(other_text)
        if config.switch_layout_after_fix:
            self._platform.switch_layout(target)

        with self._lock:
            self._run.swap_after_fix()

    def _fix_selection(self, config: AppConfig) -> None:
        """Fixes the selected text through the clipboard. run_action clears the run afterwards."""
        with self._lock:
            previous = self._last_selection_fix
            self._last_selection_fix = None

        foreground: ForegroundWindow = self._platform.foreground_info()
        if foreground.is_blocked_by_elevation:
            self._platform.notify(ADMINISTRATOR_WINDOW)
            return

        if previous is not None and previous.window == foreground.window and not foreground.is_console:
            self._platform.send_shortcut(Shortcut.UNDO)
            if config.switch_layout_after_fix:
                self._platform.switch_layout(previous.source_layout)
            return

        try:
            saved = self._platform.save_clipboard()
        except ClipboardUnavailableError:
            self._platform.notify(CLIPBOARD_BUSY)
            return

        conversion: Conversion
        try:
            sequence = self._platform.clipboard_sequence()
            self._platform.send_shortcut(Shortcut.COPY)
            if not self._wait_for_clipboard_change(sequence, config.clipboard_timeout_ms):
                return

            copied = self._platform.read_clipboard_text()
            converted = self._converter.convert(copied) if copied is not None else None
            if copied is None or converted is None or converted.text == copied:
                self._platform.restore_clipboard(saved)
                return

            conversion = converted
            self._platform.set_clipboard_text(conversion.text)
            self._platform.send_shortcut(Shortcut.PASTE)
            self._platform.sleep(config.paste_restore_delay_ms)
            self._platform.restore_clipboard(saved)
        except ClipboardUnavailableError:
            self._try_restore_clipboard(saved)
            self._platform.notify(CLIPBOARD_BUSY)
            return

        if config.switch_layout_after_fix:
            self._platform.switch_layout(conversion.target)
        with self._lock:
            self._last_selection_fix = _SelectionFix(foreground.window, conversion.target.other())

    def _wait_for_clipboard_change(self, sequence: int, timeout_ms: int) -> bool:
        """True once the clipboard sequence number moves; false after the timeout (nothing was selected)."""
        waited = 0
        while True:
            if self._platform.clipboard_sequence() != sequence:
                return True
            if waited >= timeout_ms:
                return False
            self._platform.sleep(_CLIPBOARD_POLL_MS)
            waited += _CLIPBOARD_POLL_MS

    def _try_restore_clipboard(self, saved: object) -> None:
        try:
            self._platform.restore_clipboard(saved)
        except ClipboardUnavailableError:
            # Still locked. The ClipboardBusy notification that follows covers it.
            pass
