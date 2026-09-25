"""Parses config text over the defaults from shared/config.default.json."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

from .key_names import HOLD_KEY_NAMES, HOLD_KEY_ORDER, HoldKeys, KeyNames, ascii_lower

_ASCII_DIGITS = frozenset("0123456789")
_ASCII_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1
_INT64_DIGITS = 19
"""Most digits a 64-bit integer can have; longer text never parses as one."""
_MAX_JSON_DEPTH = 64
"""JsonDocument.Parse's default MaxDepth, which the C# parser leans on; the root object is depth 1."""
_DOT_NET_WHITESPACE = (
    "\t\n\v\f\r \u0085\u00a0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000"
)
"""What .NET's string.Trim() removes (char.IsWhiteSpace). Python's str.strip() also removes
U+001C to U+001F, so hotkey parts are trimmed with this set instead."""


@dataclass(frozen=True)
class Chord:
    """A set of hold keys plus one trigger key."""

    hold: HoldKeys
    trigger_vk: int

    def format(self, names: KeyNames) -> str:
        """Canonical hotkey text: hold keys in the order Shift, Ctrl, Alt, Win, CapsLock, then the trigger."""
        parts = [HOLD_KEY_NAMES[hold] for hold in HOLD_KEY_ORDER if hold in self.hold]
        parts.append(names.name_of(self.trigger_vk))
        return "+".join(parts)


@dataclass(frozen=True)
class AppConfig:
    """A valid config. Layouts are "auto" or 8 uppercase hex digits."""

    enabled: bool
    fix_typed: Chord
    fix_selection: Chord
    switch_layout_after_fix: bool
    latin_layout: str
    arabic_layout: str
    max_run_length: int
    clipboard_timeout_ms: int
    paste_restore_delay_ms: int
    release_timeout_ms: int


@dataclass(frozen=True)
class ConfigError:
    code: str
    message: str


@dataclass(frozen=True)
class ConfigResult:
    """Exactly one of config and error is set."""

    config: AppConfig | None
    error: ConfigError | None


@dataclass(frozen=True)
class _JsonObject:
    """A parsed JSON object, keeping its fields in document order, repeats included."""

    fields: tuple[tuple[str, Any], ...]


@dataclass(frozen=True)
class _JsonNumber:
    """A parsed JSON number, kept as written so whole numbers can be told apart."""

    raw: str


def _reject_constant(name: str) -> Any:
    """NaN and Infinity are not JSON, so the parser rejects them like JsonDocument does."""
    raise ValueError(f"'{name}' is not a valid JSON value.")


def _parse_json(text: str) -> Any:
    return json.loads(
        text,
        object_pairs_hook=lambda pairs: _JsonObject(tuple(pairs)),
        parse_int=_JsonNumber,
        parse_float=_JsonNumber,
        parse_constant=_reject_constant,
    )


def _is_nested_too_deeply(root: Any) -> bool:
    """True when nesting passes the parser's depth limit. Walks iteratively so deep input can't overflow."""
    pending: list[tuple[Any, int]] = [(root, 1)]
    while pending:
        value, depth = pending.pop()
        if isinstance(value, _JsonObject):
            children: list[Any] = [field_value for _, field_value in value.fields]
        elif isinstance(value, list):
            children = value
        else:
            continue
        if depth > _MAX_JSON_DEPTH:
            return True
        pending.extend((child, depth + 1) for child in children)
    return False


def _for_each_field(
    element: _JsonObject,
    apply: Callable[[str, Any], ConfigError | None],
) -> ConfigError | None:
    for name, value in element.fields:
        error = apply(name, value)
        if error is not None:
            return error
    return None


def _unknown_field(path: str) -> ConfigError:
    return ConfigError("field.unknown", f'Unknown setting "{path}".')


def _type_error(path: str, expected: str) -> ConfigError:
    return ConfigError("field.type", f"{path} must be {expected}.")


def _read_object(
    value: Any,
    path: str,
    apply: Callable[[_JsonObject], ConfigError | None],
) -> ConfigError | None:
    return apply(value) if isinstance(value, _JsonObject) else _type_error(path, "an object")


def _read_bool(value: Any, path: str, set_value: Callable[[bool], None]) -> ConfigError | None:
    if not isinstance(value, bool):
        return _type_error(path, "true or false")
    set_value(value)
    return None


def _read_int(
    value: Any,
    path: str,
    minimum: int,
    maximum: int,
    set_value: Callable[[int], None],
) -> ConfigError | None:
    raw = value.raw if isinstance(value, _JsonNumber) else ""
    digits = raw[1:] if raw.startswith("-") else raw
    if not digits or not all(char in _ASCII_DIGITS for char in digits):
        return _type_error(path, "a whole number")
    out_of_range = ConfigError("number.range", f"{path} must be from {minimum} to {maximum}.")
    if len(digits) > _INT64_DIGITS:
        return out_of_range
    number = int(raw)
    if not _INT64_MIN <= number <= _INT64_MAX or number < minimum or number > maximum:
        return out_of_range
    set_value(number)
    return None


def _read_layout(value: Any, path: str, set_value: Callable[[str], None]) -> ConfigError | None:
    if not isinstance(value, str):
        return _type_error(path, "a string")
    if ascii_lower(value) == "auto":
        set_value("auto")
        return None
    if len(value) == 8 and all(char in _ASCII_HEX_DIGITS for char in value):
        set_value(value.upper())
        return None
    return ConfigError(
        "layout.invalid",
        f'{path} must be "auto" or 8 hex digits such as "04090409", not "{value}".',
    )


def _find_repeated_field(value: Any, prefix: str) -> str | None:
    """The path of the first field name repeated within one object, anywhere in the document."""
    if isinstance(value, list):
        for item in value:
            in_item = _find_repeated_field(item, prefix)
            if in_item is not None:
                return in_item
        return None
    if not isinstance(value, _JsonObject):
        return None
    seen: set[str] = set()
    for name, field_value in value.fields:
        if name in seen:
            return prefix + name
        seen.add(name)
        in_field = _find_repeated_field(field_value, prefix + name + ".")
        if in_field is not None:
            return in_field
    return None


@dataclass(slots=True)
class _Builder:
    """A config under construction. Every field is None until set."""

    enabled: bool | None = None
    fix_typed: Chord | None = None
    fix_selection: Chord | None = None
    switch_layout_after_fix: bool | None = None
    latin_layout: str | None = None
    arabic_layout: str | None = None
    max_run_length: int | None = None
    clipboard_timeout_ms: int | None = None
    paste_restore_delay_ms: int | None = None
    release_timeout_ms: int | None = None

    @classmethod
    def starting_from(cls, start: AppConfig) -> _Builder:
        return cls(
            enabled=start.enabled,
            fix_typed=start.fix_typed,
            fix_selection=start.fix_selection,
            switch_layout_after_fix=start.switch_layout_after_fix,
            latin_layout=start.latin_layout,
            arabic_layout=start.arabic_layout,
            max_run_length=start.max_run_length,
            clipboard_timeout_ms=start.clipboard_timeout_ms,
            paste_restore_delay_ms=start.paste_restore_delay_ms,
            release_timeout_ms=start.release_timeout_ms,
        )

    def build(self) -> AppConfig | None:
        if (
            self.enabled is None
            or self.fix_typed is None
            or self.fix_selection is None
            or self.switch_layout_after_fix is None
            or self.latin_layout is None
            or self.arabic_layout is None
            or self.max_run_length is None
            or self.clipboard_timeout_ms is None
            or self.paste_restore_delay_ms is None
            or self.release_timeout_ms is None
        ):
            return None
        return AppConfig(
            self.enabled,
            self.fix_typed,
            self.fix_selection,
            self.switch_layout_after_fix,
            self.latin_layout,
            self.arabic_layout,
            self.max_run_length,
            self.clipboard_timeout_ms,
            self.paste_restore_delay_ms,
            self.release_timeout_ms,
        )


class ConfigParser:
    """Parses config text over the defaults from shared/config.default.json."""

    def __init__(self, names: KeyNames, default_json: str) -> None:
        self._names = names
        builder = _Builder()
        error = self._apply(default_json, builder)
        if error is not None:
            raise ValueError(f"The default config is invalid: {error.code}: {error.message}")
        defaults = builder.build()
        if defaults is None:
            raise ValueError("The default config must set every field.")
        self._defaults = defaults

    @property
    def defaults(self) -> AppConfig:
        return self._defaults

    def parse(self, json_text: str) -> ConfigResult:
        builder = _Builder.starting_from(self._defaults)
        error = self._apply(json_text, builder)
        if error is not None:
            return ConfigResult(None, error)
        return ConfigResult(builder.build(), None)

    def parse_chord(self, text: str, path: str) -> tuple[Chord | None, ConfigError | None]:
        """Parses a hotkey string such as "Shift+CapsLock+Tab"."""
        parts = [part.strip(_DOT_NET_WHITESPACE) for part in text.split("+")]
        hold = HoldKeys.NONE
        for part in parts[:-1]:
            key = self._names.hold_key(part)
            if key is not None:
                hold |= key
            elif self._names.is_modifier_name(part) or self._names.trigger_vk(part) is not None:
                return None, ConfigError(
                    "hotkey.notHoldKey",
                    f'{path}: "{part}" can\'t be held. Hold keys are Shift, Ctrl, Alt, Win and CapsLock.',
                )
            else:
                return None, ConfigError("hotkey.unknownKey", f'{path}: unknown key "{part}".')

        trigger = parts[-1]
        if self._names.is_modifier_name(trigger):
            return None, ConfigError(
                "hotkey.triggerIsModifier",
                f'{path}: the last key, "{trigger}", must not be a modifier.',
            )
        vk = self._names.trigger_vk(trigger)
        if vk is None:
            return None, ConfigError("hotkey.unknownKey", f'{path}: unknown key "{trigger}".')
        if hold == HoldKeys.NONE:
            return None, ConfigError(
                "hotkey.noHoldKey",
                f"{path}: add at least one hold key (Shift, Ctrl, Alt, Win or CapsLock).",
            )
        return Chord(hold, vk), None

    def _apply(self, json_text: str, config: _Builder) -> ConfigError | None:
        try:
            root = _parse_json(json_text)
        except (ValueError, RecursionError) as exception:
            return ConfigError("json.invalid", f"The config is not valid JSON: {exception}")

        if _is_nested_too_deeply(root):
            return ConfigError(
                "json.invalid", f"The config is nested more than {_MAX_JSON_DEPTH} levels deep."
            )
        if not isinstance(root, _JsonObject):
            return ConfigError("json.invalid", "The config must be a JSON object.")
        repeated = _find_repeated_field(root, "")
        if repeated is not None:
            return ConfigError("json.invalid", f"{repeated} appears more than once.")
        error = self._apply_root(root, config)
        if error is not None:
            return error

        if (
            config.fix_typed is not None
            and config.fix_selection is not None
            and config.fix_typed == config.fix_selection
        ):
            return ConfigError(
                "hotkey.duplicate",
                "hotkeys.fixTyped and hotkeys.fixSelection are the same chord.",
            )
        return None

    def _apply_root(self, root: _JsonObject, config: _Builder) -> ConfigError | None:
        def apply(name: str, value: Any) -> ConfigError | None:
            if name == "enabled":
                return _read_bool(value, "enabled", partial(setattr, config, "enabled"))
            if name == "hotkeys":
                return _read_object(value, "hotkeys", lambda hotkeys: _for_each_field(hotkeys, apply_hotkey))
            if name == "switchLayoutAfterFix":
                return _read_bool(
                    value, "switchLayoutAfterFix", partial(setattr, config, "switch_layout_after_fix")
                )
            if name == "layouts":
                return _read_object(value, "layouts", lambda layouts: _for_each_field(layouts, apply_layout))
            if name == "maxRunLength":
                return _read_int(value, "maxRunLength", 10, 10000, partial(setattr, config, "max_run_length"))
            if name == "clipboardTimeoutMs":
                return _read_int(
                    value, "clipboardTimeoutMs", 50, 10000, partial(setattr, config, "clipboard_timeout_ms")
                )
            if name == "pasteRestoreDelayMs":
                return _read_int(
                    value, "pasteRestoreDelayMs", 50, 10000, partial(setattr, config, "paste_restore_delay_ms")
                )
            if name == "releaseTimeoutMs":
                return _read_int(
                    value, "releaseTimeoutMs", 50, 10000, partial(setattr, config, "release_timeout_ms")
                )
            return _unknown_field(name)

        def apply_hotkey(name: str, value: Any) -> ConfigError | None:
            if name == "fixTyped":
                return self._read_chord(value, "hotkeys.fixTyped", partial(setattr, config, "fix_typed"))
            if name == "fixSelection":
                return self._read_chord(value, "hotkeys.fixSelection", partial(setattr, config, "fix_selection"))
            return _unknown_field("hotkeys." + name)

        def apply_layout(name: str, value: Any) -> ConfigError | None:
            if name == "latin":
                return _read_layout(value, "layouts.latin", partial(setattr, config, "latin_layout"))
            if name == "arabic":
                return _read_layout(value, "layouts.arabic", partial(setattr, config, "arabic_layout"))
            return _unknown_field("layouts." + name)

        return _for_each_field(root, apply)

    def _read_chord(self, value: Any, path: str, set_value: Callable[[Chord], None]) -> ConfigError | None:
        if not isinstance(value, str):
            return _type_error(path, "a string")
        chord, error = self.parse_chord(value, path)
        if error is not None:
            return error
        assert chord is not None, "parse_chord returns a chord whenever it returns no error."
        set_value(chord)
        return None
