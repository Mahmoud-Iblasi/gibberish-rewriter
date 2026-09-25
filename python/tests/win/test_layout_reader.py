"""Mirrors csharp/tests/GibberishRewriter.App.Tests/LayoutReaderTests.cs.

The two tests the C# marks [LayoutPairFact] are marked the same way here: they need GIBBERISH_INTEGRATION=1 and
both English (US) 04090409 and Arabic (101) 04012C01 installed. The calls this module makes are all read-only --
GetKeyboardLayoutList, MapVirtualKeyEx and ToUnicodeEx with flag 4 -- so the rest run every time.
"""

from __future__ import annotations

import json
import os
import pathlib

import pytest
from gibberish_rewriter.core.key_names import KeyNames
from gibberish_rewriter.core.key_table import KeyState

from gibberish_rewriter.win import layout_reader, win32
from gibberish_rewriter.win.hkl import LayoutPair
from gibberish_rewriter.win.layout_reader import DeadKeyError

ENGLISH = 0x04090409
ARABIC = 0x04012C01

SHARED = pathlib.Path(__file__).resolve().parents[3] / "shared"
"""The folder both apps are tested against; the C# copies it next to its binaries instead."""

INTEGRATION = os.environ.get("GIBBERISH_INTEGRATION") == "1"


def _layout_pair_skip() -> str | None:
    if not INTEGRATION:
        return "Windows integration test. Set GIBBERISH_INTEGRATION=1 to run it."
    installed = layout_reader.installed_layouts()
    if ENGLISH not in installed or ARABIC not in installed:
        return "English (US) 04090409 and Arabic (101) 04012C01 aren't both installed."
    return None


_SKIP = _layout_pair_skip()
needs_layout_pair = pytest.mark.skipif(_SKIP is not None, reason=_SKIP or "")


@pytest.fixture(scope="module")
def names() -> KeyNames:
    return KeyNames.load(SHARED / "keys.json")


@needs_layout_pair
def test_the_table_read_from_windows_equals_the_snapshot(names):
    table = layout_reader.read_table(names, LayoutPair(ENGLISH, ARABIC))
    expected = json.loads((SHARED / "layouts" / "us-arabic101.json").read_text(encoding="utf-8"))
    assert json.loads(table.to_json()) == expected


@needs_layout_pair
def test_key_a_tells_the_snapshot_layouts_apart():
    installed = layout_reader.installed_with_key_a()
    assert (ENGLISH, "a") in installed
    assert (ARABIC, "ش") in installed


def test_installed_layouts_are_low_32_bit_values_in_windows_order():
    installed = layout_reader.installed_layouts()
    assert installed, "Windows always has at least one layout"
    assert all(0 <= layout <= 0xFFFFFFFF for layout in installed)
    assert len(set(installed)) == len(installed)


def test_installed_layouts_asks_windows_for_the_count_before_the_list(monkeypatch):
    calls: list[int] = []

    def fake(size, buffer):
        calls.append(size)
        if buffer is not None:
            buffer[0] = 0x04090409
        return 1

    monkeypatch.setattr(win32, "GetKeyboardLayoutList", fake)
    assert layout_reader.installed_layouts() == (0x04090409,)
    assert calls == [0, 1]


def test_installed_layouts_keeps_only_what_the_second_call_filled(monkeypatch):
    """The second call can report fewer layouts than the first, and the C# takes only that many."""

    def fake(size, buffer):
        if buffer is None:
            return 3
        buffer[0] = 0x04090409
        return 1

    monkeypatch.setattr(win32, "GetKeyboardLayoutList", fake)
    assert layout_reader.installed_layouts() == (0x04090409,)


def test_installed_layouts_never_reads_past_the_array_it_allocated(monkeypatch):
    """A count that grew between the two calls would run off the end of a Python array, unlike a C# Take."""

    def fake(size, buffer):
        return 1 if buffer is None else 9

    monkeypatch.setattr(win32, "GetKeyboardLayoutList", fake)
    assert len(layout_reader.installed_layouts()) == 1


def test_installed_layouts_drops_the_sign_extension(monkeypatch):
    def fake(size, buffer):
        if buffer is None:
            return 1
        buffer[0] = 0xFFFFFFFFF0C00409
        return 1

    monkeypatch.setattr(win32, "GetKeyboardLayoutList", fake)
    assert layout_reader.installed_layouts() == (0xF0C00409,)


def test_installed_with_key_a_reports_one_entry_per_installed_layout():
    installed = layout_reader.installed_with_key_a()
    assert tuple(layout for layout, _ in installed) == layout_reader.installed_layouts()
    assert all(isinstance(key_a, str) for _, key_a in installed)


def test_a_dead_key_a_leaves_the_layout_with_an_empty_name(monkeypatch):
    """The C# swallows DeadKeyException here so one unsupported layout can't stop "auto" from choosing."""
    monkeypatch.setattr(win32, "GetKeyboardLayoutList", lambda size, buffer: _one(size, buffer, ENGLISH))

    def dead(*args):
        raise DeadKeyError(ENGLISH, "KeyA")

    monkeypatch.setattr(layout_reader, "read_text", dead)
    assert layout_reader.installed_with_key_a() == ((ENGLISH, ""),)


def _one(size, buffer, value):
    if buffer is None:
        return 1
    buffer[0] = value
    return 1


def test_read_text_asks_for_the_low_byte_of_the_scan_code_only(monkeypatch):
    """An 0xE0 prefix sets the high bit, which ToUnicodeEx reads as a key release."""
    seen: list[int] = []
    monkeypatch.setattr(win32, "MapVirtualKeyEx", lambda vk, map_type, handle: 0xE035)
    monkeypatch.setattr(
        win32,
        "ToUnicodeEx",
        lambda vk, scan, state, buffer, length, flags, handle: seen.append(scan) or 0,
    )
    layout_reader.read_text(ENGLISH, "NumpadDivide", 0x6F, KeyState.PLAIN)
    assert seen == [0x35]


def test_read_text_asks_for_the_extended_mapping_and_leaves_the_keyboard_alone(monkeypatch):
    asked: list[tuple[int, int]] = []
    monkeypatch.setattr(
        win32, "MapVirtualKeyEx", lambda vk, map_type, handle: asked.append((vk, map_type)) or 0x1E
    )
    flags: list[int] = []
    monkeypatch.setattr(
        win32,
        "ToUnicodeEx",
        lambda vk, scan, state, buffer, length, wflags, handle: flags.append(wflags) or 0,
    )
    layout_reader.read_text(ENGLISH, "KeyA", 0x41, KeyState.PLAIN)
    assert asked == [(0x41, win32.MAPVK_VK_TO_VSC_EX)]
    assert flags == [4]


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (KeyState.PLAIN, {0x90: 0x01}),
        (KeyState.SHIFT, {0x90: 0x01, 0x10: 0x80, 0xA0: 0x80}),
        (KeyState.CAPS, {0x90: 0x01, 0x14: 0x01}),
        (KeyState.SHIFT_CAPS, {0x90: 0x01, 0x10: 0x80, 0xA0: 0x80, 0x14: 0x01}),
    ],
)
def test_the_key_state_passed_matches_the_modifier_state(monkeypatch, state, expected):
    """NumLock on, Shift as both VK_SHIFT and VK_LSHIFT, Caps Lock as the toggle bit."""
    seen: list[dict[int, int]] = []

    def capture(vk, scan, key_state, buffer, length, flags, handle):
        seen.append({index: key_state[index] for index in range(256) if key_state[index]})
        return 0

    monkeypatch.setattr(win32, "MapVirtualKeyEx", lambda vk, map_type, handle: 0x1E)
    monkeypatch.setattr(win32, "ToUnicodeEx", capture)
    layout_reader.read_text(ENGLISH, "KeyA", 0x41, state)
    assert seen == [expected]


def test_a_negative_result_is_a_dead_key(monkeypatch):
    monkeypatch.setattr(win32, "MapVirtualKeyEx", lambda vk, map_type, handle: 0x1E)
    monkeypatch.setattr(win32, "ToUnicodeEx", lambda *args: -1)
    with pytest.raises(DeadKeyError) as raised:
        layout_reader.read_text(0x0000040C, "KeyA", 0x41, KeyState.PLAIN)
    assert raised.value.layout == 0x0000040C
    assert str(raised.value) == "Layout 0000040C has a dead key: KeyA."


def test_a_key_that_types_nothing_gives_the_empty_string(monkeypatch):
    monkeypatch.setattr(win32, "MapVirtualKeyEx", lambda vk, map_type, handle: 0x1E)
    monkeypatch.setattr(win32, "ToUnicodeEx", lambda *args: 0)
    assert layout_reader.read_text(ENGLISH, "F13", 0x7C, KeyState.PLAIN) == ""


def test_read_text_reads_a_real_layout():
    """ToUnicodeEx with flag 4 changes nothing, so this needs no desktop and no integration flag."""
    installed = layout_reader.installed_layouts()
    text = layout_reader.read_text(installed[0], "KeyA", 0x41, KeyState.PLAIN)
    assert len(text) <= 1


def test_read_table_rejects_a_table_key_that_is_not_a_key_name():
    """The C# throws InvalidOperationException; a wrong keys.json is a startup error either way."""
    names = KeyNames({"KeyA": 0x41}, {}, {}, ["KeyA", "KeyNope"])
    with pytest.raises(ValueError, match="tableKeys lists unknown key KeyNope"):
        layout_reader.read_table(names, LayoutPair(ENGLISH, ARABIC))


def test_read_table_labels_the_snapshot_with_the_pairs_hkl_values(monkeypatch):
    monkeypatch.setattr(layout_reader, "read_text", lambda layout, key, vk, state: "x")
    names = KeyNames({"KeyA": 0x41}, {}, {}, ["KeyA"])
    table = layout_reader.read_table(names, LayoutPair(ENGLISH, ARABIC))
    assert (table.latin_hkl, table.arabic_hkl) == ("04090409", "04012C01")
    assert [entry.key for entry in table.keys] == ["KeyA"]
    assert table.keys[0].vk == 0x41
    assert table.keys[0].latin == ("x", "x", "x", "x")


def test_read_table_reads_each_key_in_four_states_on_both_layouts(monkeypatch):
    asked: list[tuple[int, str, int, KeyState]] = []
    monkeypatch.setattr(
        layout_reader,
        "read_text",
        lambda layout, key, vk, state: asked.append((layout, key, vk, state)) or "",
    )
    names = KeyNames({"KeyA": 0x41}, {}, {}, ["KeyA"])
    layout_reader.read_table(names, LayoutPair(ENGLISH, ARABIC))
    assert [(layout, state) for layout, _, _, state in asked] == [
        (ENGLISH, KeyState.PLAIN),
        (ENGLISH, KeyState.SHIFT),
        (ENGLISH, KeyState.CAPS),
        (ENGLISH, KeyState.SHIFT_CAPS),
        (ARABIC, KeyState.PLAIN),
        (ARABIC, KeyState.SHIFT),
        (ARABIC, KeyState.CAPS),
        (ARABIC, KeyState.SHIFT_CAPS),
    ]
