import pytest

import shared_files
from gibberish_rewriter.core.key_names import HoldKeys, KeyNames
from gibberish_rewriter.core.key_table import KeyTable

NAMES = KeyNames.load(shared_files.path_of("keys.json"))
TABLE = KeyTable.load(shared_files.path_of("layouts/us-arabic101.json"))


@pytest.mark.parametrize(
    ("name", "expected"),
    [("Tab", 0x09), ("tab", 0x09), ("KEYQ", 0x51), ("Backquote", 0xC0), ("`", 0xC0), ("F24", 0x87), ("NumpadDivide", 0x6F)],
)
def test_trigger_names_are_case_insensitive_and_accept_a_backtick(name, expected):
    assert NAMES.trigger_vk(name) == expected


@pytest.mark.parametrize("name", ["ShiftLeft", "Shift", "CapsLock", "NumLock"])
def test_modifier_names_are_not_triggers(name):
    assert NAMES.trigger_vk(name) is None
    assert NAMES.is_modifier_name(name)


@pytest.mark.parametrize(("name", "expected"), [("ShiftLeft", 0xA0), ("MetaRight", 0x5C), ("KeyA", 0x41)])
def test_vk_of_finds_modifiers_and_other_keys(name, expected):
    assert NAMES.vk_of(name) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [("shift", HoldKeys.SHIFT), ("Ctrl", HoldKeys.CTRL), ("WIN", HoldKeys.WIN), ("capslock", HoldKeys.CAPS_LOCK)],
)
def test_hold_key_names_are_case_insensitive(name, expected):
    assert NAMES.hold_key(name) == expected


def test_names_ignore_case_for_ascii_letters_only():
    assert NAMES.trigger_vk("Dıgıt1") is None
    assert NAMES.hold_key("ſhift") is None


@pytest.mark.parametrize(
    ("vk", "expected"),
    [
        (0xA0, HoldKeys.SHIFT),
        (0xA1, HoldKeys.SHIFT),
        (0x10, HoldKeys.SHIFT),
        (0xA3, HoldKeys.CTRL),
        (0xA5, HoldKeys.ALT),
        (0x5C, HoldKeys.WIN),
        (0x14, HoldKeys.CAPS_LOCK),
        (0x41, HoldKeys.NONE),
    ],
)
def test_hold_key_of_maps_left_right_and_sideless_codes(vk, expected):
    assert NAMES.hold_key_of(vk) == expected


@pytest.mark.parametrize(
    ("vk", "expected"),
    [(0x90, True), (0x91, True), (0x14, True), (0xA2, True), (0x11, True), (0x41, False), (0x09, False)],
)
def test_is_modifier_covers_hold_keys_and_lock_keys(vk, expected):
    assert NAMES.is_modifier(vk) == expected


def test_vks_of_lists_codes_in_canonical_order():
    assert NAMES.vks_of(HoldKeys.CAPS_LOCK | HoldKeys.SHIFT) == [0xA0, 0xA1, 0x10, 0x14]


@pytest.mark.parametrize(("vk", "expected"), [(0xC0, "Backquote"), (0xA0, "ShiftLeft"), (0xE8, "0xE8")])
def test_name_of_returns_the_name_from_keys_json(vk, expected):
    assert NAMES.name_of(vk) == expected


def test_table_keys_are_the_snapshot_keys_in_order():
    assert list(NAMES.table_keys) == [entry.key for entry in TABLE.keys]


def test_every_table_key_has_its_snapshot_code():
    for entry in TABLE.keys:
        assert NAMES.trigger_vk(entry.key) == entry.vk


def test_parse_rejects_a_table_key_missing_from_keys():
    with pytest.raises(ValueError):
        KeyNames.parse('{ "keys": { "KeyA": 65 }, "modifiers": {}, "holdKeys": {}, "tableKeys": [ "KeyB" ] }')
