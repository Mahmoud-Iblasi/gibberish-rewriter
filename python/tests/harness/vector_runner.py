"""Feeds one vector's events to a real Engine with a FakePlatform (plan Task 10, vector harness rules)."""

from __future__ import annotations

import json
from collections import deque
from typing import Any

import shared_files
from gibberish_rewriter.core.chord_detector import ChordAction
from gibberish_rewriter.core.config import AppConfig, Chord, ConfigParser
from gibberish_rewriter.core.engine import Engine, KeyEvent
from gibberish_rewriter.core.key_names import HOLD_KEY_ORDER, VK_PACKET, HoldKeys, KeyNames
from gibberish_rewriter.core.key_table import KeyTable, LayoutKind
from gibberish_rewriter.core.text_converter import TextConverter
from gibberish_rewriter.core.word_list import WordList

from harness.fake_platform import FakePlatform

NAMES = KeyNames.load(shared_files.path_of("keys.json"))
TABLE = KeyTable.load(shared_files.path_of("layouts/us-arabic101.json"))
CONVERTER = TextConverter(TABLE, WordList.load(shared_files.path_of("wordlists/english.txt")))
PARSER = ConfigParser(NAMES, shared_files.read_text("config.default.json"))

_HOLD_KEY_NAMES = {
    HoldKeys.SHIFT: "ShiftLeft",
    HoldKeys.CTRL: "ControlLeft",
    HoldKeys.ALT: "AltLeft",
    HoldKeys.WIN: "MetaLeft",
}


def load_vectors(relative: str) -> list[dict[str, Any]]:
    """Every vector of one file, in order. Names are unique within a file, as the C# loader also demands."""
    vectors: list[dict[str, Any]] = json.loads(shared_files.read_text(relative))
    names = [vector["name"] for vector in vectors]
    if len(set(names)) != len(names):
        raise ValueError(f"Vector names are not unique in {relative}.")
    return vectors


def vector_named(relative: str, name: str) -> dict[str, Any]:
    """The one vector of a file with this name."""
    return next(vector for vector in load_vectors(relative) if vector["name"] == name)


def _flag(vector: dict[str, Any], name: str) -> bool:
    """An optional boolean field, false when it is missing. Only a JSON boolean counts, as C# GetBoolean demands."""
    value = vector.get(name, False)
    if not isinstance(value, bool):
        raise ValueError(f"Vector field {name!r} must be a JSON boolean, not {json.dumps(value)}.")
    return value


def _call_value(value: Any) -> str:
    """One expected-call value, as the C# renders it: GetInt32 for a number, GetString for the rest, so a JSON
    null becomes an empty string and a boolean is an error."""
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    raise ValueError(f"Expected call value must be a string, a null or an integer, not {json.dumps(value)}.")


def _parse_layout(name: str) -> LayoutKind | None:
    return None if name == "other" else LayoutKind.parse(name)


def _hold_key_name(hold: HoldKeys) -> str:
    return _HOLD_KEY_NAMES.get(hold, "CapsLock")


class VectorRunner:
    """Feeds one vector's events to a real Engine with a FakePlatform (plan Task 10, vector harness rules)."""

    def __init__(self, vector: dict[str, Any]) -> None:
        self._down: set[int] = set()
        self._started: deque[ChordAction] = deque()
        self.decisions: list[str] = []
        """One decision string per key event."""

        config_text = json.dumps(vector["config"]) if "config" in vector else "{}"
        config = PARSER.parse(config_text).config
        if config is None:
            raise ValueError(f"Invalid config in vector: {config_text}")
        self.config: AppConfig = config

        self.platform = FakePlatform()
        self.platform.layout = _parse_layout(vector["layout"]) if "layout" in vector else LayoutKind.LATIN
        self.platform.is_console = _flag(vector, "console")
        self.platform.is_blocked_by_elevation = _flag(vector, "blockedByElevation")
        self.platform.release_in_time = not _flag(vector, "releaseTimeout")
        self.platform.clipboard_text = vector.get("clipboard")
        self.platform.selection = vector.get("selection")
        self.platform.clipboard_locked = vector.get("clipboardLocked")

        self.engine = Engine(
            NAMES,
            TABLE,
            CONVERTER,
            self.config,
            self.platform,
            self._started.append,
            _flag(vector, "capsLock"),
        )

    @staticmethod
    def expected_calls(vector: dict[str, Any]) -> list[str]:
        """Expected platform calls of a vector, as strings comparable with FakePlatform.calls."""
        calls = []
        for call in vector["expect"]:
            ((field, value),) = call.items()
            calls.append(f"{field} {_call_value(value)}")
        return calls

    def run(self, events: list[dict[str, Any]]) -> None:
        for event in events:
            self._feed(event)

    def _feed(self, event: dict[str, Any]) -> None:
        if "tap" in event:
            shift = _flag(event, "shift")
            if shift:
                self._key("ShiftLeft", True)
            self._key(event["tap"], True)
            self._key(event["tap"], False)
            if shift:
                self._key("ShiftLeft", False)
        elif "down" in event:
            self._key(event["down"], True)
        elif "up" in event:
            self._key(event["up"], False)
        elif "chord" in event:
            self._press_chord(event["chord"], event.get("during"))
        elif "mouseDown" in event:
            self.engine.on_mouse_down()
        elif "window" in event:
            self.platform.window = event["window"]
        elif "layout" in event:
            self.platform.layout = _parse_layout(event["layout"])
        elif "packet" in event:
            for _ in event["packet"]:
                self._send(VK_PACKET, True, is_packet=True)
                self._send(VK_PACKET, False, is_packet=True)
        elif "enabled" in event:
            self.engine.enabled = event["enabled"]
        elif "capsLock" in event:
            self.engine.set_caps_lock_on(event["capsLock"])
        elif "elevated" in event:
            self.platform.is_blocked_by_elevation = event["elevated"]
        elif "missedInput" in event:
            self.engine.reset_after_missed_input(event["missedInput"]["capsLock"])
        elif "config" in event:
            # The C# passes the vector's raw JSON text; re-serializing parses to the same config, and the parser's
            # own contract is covered by the 53 config vectors. Settled by the controller, not an oversight.
            config_text = json.dumps(event["config"])
            config = PARSER.parse(config_text).config
            if config is None:
                raise ValueError(f"Invalid config event: {config_text}")
            self.config = config
            self.engine.apply_config(config)
        else:
            raise ValueError(f"Unknown vector event: {json.dumps(event)}")

    def _press_chord(self, name: str, during: list[dict[str, Any]] | None) -> None:
        chord: Chord
        if name == "fixTyped":
            chord = self.config.fix_typed
        elif name == "fixSelection":
            chord = self.config.fix_selection
        else:
            raise ValueError(f"Unknown chord {name!r}.")
        holds = [_hold_key_name(hold) for hold in HOLD_KEY_ORDER if hold in chord.hold]
        trigger = NAMES.name_of(chord.trigger_vk)

        for hold in holds:
            self._key(hold, True)
        if during is not None:
            self.platform.during_action = lambda: self.run(during)
        self._key(trigger, True)
        self.platform.during_action = None
        self._key(trigger, False)
        for hold in reversed(holds):
            self._key(hold, False)

    def _key(self, name: str, down: bool) -> None:
        vk = NAMES.vk_of(name)
        if vk is None:
            raise ValueError(f"Unknown key name {name!r} in vector.")
        self._send(vk, down, is_packet=False)

    def _send(self, vk: int, down: bool, is_packet: bool) -> None:
        modifiers = HoldKeys.NONE
        for held in self._down:
            modifiers |= NAMES.hold_key_of(held)
        modifiers &= ~HoldKeys.CAPS_LOCK

        decision = self.engine.on_key(
            KeyEvent(vk, down, False, is_packet, modifiers, self.platform.window, self.platform.layout)
        )
        if down:
            self._down.add(vk)
        else:
            self._down.discard(vk)

        started = list(self._started)
        self._started.clear()

        text = "swallow" if decision.swallow else "pass"
        for action in started:
            text += " fire:fixTyped" if action is ChordAction.FIX_TYPED else " fire:fixSelection"
        for sent in decision.send_keys:
            text += " send:" + NAMES.name_of(sent)
        self.decisions.append(text)

        for action in started:
            self.engine.run_action(action)
