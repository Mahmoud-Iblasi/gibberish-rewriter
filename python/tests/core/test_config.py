import json
from typing import Any

import pytest

import shared_files
from gibberish_rewriter.core.config import AppConfig, Chord, ConfigParser
from gibberish_rewriter.core.key_names import HoldKeys, KeyNames

NAMES = KeyNames.load(shared_files.path_of("keys.json"))
PARSER = ConfigParser(NAMES, shared_files.read_text("config.default.json"))
VECTORS = json.loads(shared_files.read_text("vectors/config.json"))

_EXPECT_FIELDS = {
    "enabled": "enabled",
    "switchLayoutAfterFix": "switch_layout_after_fix",
    "latinLayout": "latin_layout",
    "arabicLayout": "arabic_layout",
    "maxRunLength": "max_run_length",
    "clipboardTimeoutMs": "clipboard_timeout_ms",
    "pasteRestoreDelayMs": "paste_restore_delay_ms",
    "releaseTimeoutMs": "release_timeout_ms",
}


def _actual(config: AppConfig, name: str, vector_name: str) -> Any:
    if name == "fixTyped":
        return config.fix_typed.format(NAMES)
    if name == "fixSelection":
        return config.fix_selection.format(NAMES)
    field = _EXPECT_FIELDS.get(name)
    if field is None:
        raise AssertionError(f"Unknown expect field '{name}' in '{vector_name}'.")
    return getattr(config, field)


@pytest.mark.parametrize("vector", VECTORS, ids=[vector["name"] for vector in VECTORS])
def test_config_vector(vector):
    result = PARSER.parse(vector["json"])

    if "error" in vector:
        assert result.config is None
        assert result.error is not None
        assert result.error.code == vector["error"]
        return

    assert result.error is None
    config = result.config
    assert config is not None
    for name, expected in vector["expect"].items():
        actual = _actual(config, name, vector["name"])
        assert type(actual) is type(expected), name
        assert actual == expected, name


def test_defaults_come_from_config_default_json():
    assert PARSER.defaults.enabled is True
    assert PARSER.defaults.fix_typed.format(NAMES) == "Shift+CapsLock+Tab"
    assert PARSER.defaults.fix_selection.format(NAMES) == "Shift+CapsLock+Backquote"
    assert PARSER.defaults.max_run_length == 1000


def test_an_incomplete_default_file_is_rejected():
    with pytest.raises(ValueError, match="must set every field"):
        ConfigParser(NAMES, "{}")


def test_nesting_deeper_than_the_parser_limit_is_rejected():
    error = PARSER.parse('{"a":' * 70 + "1" + "}" * 70).error
    assert error is not None
    assert error.code == "json.invalid"


def test_nesting_too_deep_for_the_json_parser_is_rejected_not_raised():
    error = PARSER.parse('{"a":' * 2000 + "1" + "}" * 2000).error
    assert error is not None
    assert error.code == "json.invalid"


def test_error_messages_name_the_field():
    error = PARSER.parse('{ "maxRunLength": 9 }').error
    assert error is not None
    assert "maxRunLength" in error.message


def test_chord_format_writes_hold_keys_in_canonical_order():
    chord = Chord(HoldKeys.CAPS_LOCK | HoldKeys.WIN | HoldKeys.SHIFT, 0x09)
    assert chord.format(NAMES) == "Shift+Win+CapsLock+Tab"


def test_parse_chord_accepts_a_backtick_and_mixed_case():
    chord, error = PARSER.parse_chord(" capslock + SHIFT + ` ", "test")
    assert error is None
    assert chord == Chord(HoldKeys.SHIFT | HoldKeys.CAPS_LOCK, 0xC0)
