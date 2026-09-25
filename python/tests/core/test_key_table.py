import json

import pytest

import shared_files
from gibberish_rewriter.core.key_names import KeyNames
from gibberish_rewriter.core.key_table import KeyState, KeyTable, LayoutKind, state_of

TABLE = KeyTable.load(shared_files.path_of("layouts/us-arabic101.json"))


def test_snapshot_has_the_64_keys_of_spec_4_1_with_codes_from_keys_json():
    names = KeyNames.load(shared_files.path_of("keys.json"))
    assert len(TABLE.keys) == 64
    assert TABLE.keys[0].key == "Backquote"
    assert TABLE.keys[-1].key == "NumpadDivide"
    for entry in TABLE.keys:
        assert names.trigger_vk(entry.key) == entry.vk, entry.key


def test_snapshot_records_the_layout_handles():
    assert TABLE.latin_hkl == "04090409"
    assert TABLE.arabic_hkl == "04012C01"


@pytest.mark.parametrize(
    ("vk", "layout", "state", "expected"),
    [
        (0x48, LayoutKind.ARABIC, KeyState.PLAIN, "ا"),
        (0x48, LayoutKind.LATIN, KeyState.CAPS, "H"),
        (0x48, LayoutKind.LATIN, KeyState.SHIFT_CAPS, "h"),
        (0x48, LayoutKind.ARABIC, KeyState.CAPS, "ا"),
        (0x42, LayoutKind.ARABIC, KeyState.PLAIN, "لا"),
        (0x42, LayoutKind.ARABIC, KeyState.SHIFT, "لآ"),
        (0xC0, LayoutKind.ARABIC, KeyState.SHIFT, "ّ"),
        (0xBF, LayoutKind.ARABIC, KeyState.SHIFT, "؟"),
        (0x6F, LayoutKind.LATIN, KeyState.PLAIN, "/"),
        (0x60, LayoutKind.ARABIC, KeyState.SHIFT, ""),
        (0x09, LayoutKind.LATIN, KeyState.PLAIN, ""),
    ],
)
def test_text_of_reads_the_snapshot(vk, layout, state, expected):
    assert TABLE.text_of(vk, layout, state) == expected


@pytest.mark.parametrize(
    ("text", "layout", "expected_key", "expected_state"),
    [
        ("/", LayoutKind.LATIN, "Slash", KeyState.PLAIN),
        ("?", LayoutKind.LATIN, "Slash", KeyState.SHIFT),
        ("1", LayoutKind.LATIN, "Digit1", KeyState.PLAIN),
        ("+", LayoutKind.LATIN, "Equal", KeyState.SHIFT),
        ("\\", LayoutKind.LATIN, "Backslash", KeyState.PLAIN),
        ("ل", LayoutKind.ARABIC, "KeyG", KeyState.PLAIN),
        ("لا", LayoutKind.ARABIC, "KeyB", KeyState.PLAIN),
        ("أ", LayoutKind.ARABIC, "KeyH", KeyState.SHIFT),
    ],
)
def test_find_takes_the_first_key_in_table_order_trying_plain_before_shift(text, layout, expected_key, expected_state):
    found = TABLE.find(text, layout)
    assert found is not None
    entry, state = found
    assert entry.key == expected_key
    assert state == expected_state


@pytest.mark.parametrize("text", ["", "ab", "\n"])
def test_find_returns_none_for_text_no_key_types(text):
    assert TABLE.find(text, LayoutKind.LATIN) is None


@pytest.mark.parametrize(
    ("shift", "caps_on", "expected"),
    [(False, False, KeyState.PLAIN), (True, False, KeyState.SHIFT), (False, True, KeyState.CAPS), (True, True, KeyState.SHIFT_CAPS)],
)
def test_state_of_combines_shift_and_caps_lock(shift, caps_on, expected):
    assert state_of(shift, caps_on) == expected


def test_layout_kind_helpers_round_trip():
    assert LayoutKind.LATIN.other() is LayoutKind.ARABIC
    assert LayoutKind.ARABIC.other() is LayoutKind.LATIN
    assert LayoutKind.ARABIC.value == "arabic"
    assert LayoutKind.parse("latin") is LayoutKind.LATIN
    with pytest.raises(ValueError):
        LayoutKind.parse("other")


def test_to_json_round_trips_through_parse():
    copy = KeyTable.parse(TABLE.to_json())
    assert copy.latin_hkl == TABLE.latin_hkl
    assert copy.arabic_hkl == TABLE.arabic_hkl
    assert copy.keys == TABLE.keys


def test_to_json_parses_to_the_snapshot_data():
    # Layout dumps are compared after JSON parsing: the C# writer escapes Arabic diacritics
    # as \u sequences, and this one writes them as characters.
    assert json.loads(TABLE.to_json()) == json.loads(shared_files.read_text("layouts/us-arabic101.json"))
