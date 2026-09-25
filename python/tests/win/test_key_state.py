"""win/key_state.py. The C# has no KeyStateTrackerTests; the class is pure, so it is tested here."""

from __future__ import annotations

import pytest

from gibberish_rewriter.win.key_state import KeyStateTracker


def test_nothing_is_down_to_start_with():
    tracker = KeyStateTracker()
    assert not any(tracker.is_down(vk) for vk in range(256))


def test_set_and_is_down_track_one_key_each():
    tracker = KeyStateTracker()
    tracker.set(0x14, True)
    assert tracker.is_down(0x14)
    assert not tracker.is_down(0x15)
    tracker.set(0x14, False)
    assert not tracker.is_down(0x14)


def test_clear_forgets_every_key():
    tracker = KeyStateTracker()
    for vk in (0x10, 0x11, 0x14, 0xFF):
        tracker.set(vk, True)
    tracker.clear()
    assert not any(tracker.is_down(vk) for vk in range(256))


@pytest.mark.parametrize("vk", [-1, -256, 256, 0x1000])
def test_codes_outside_the_table_are_ignored_rather_than_raising(vk):
    """The C# guards with ``(uint)vk < 256``, so a negative code is out of range too."""
    tracker = KeyStateTracker()
    tracker.set(vk, True)
    assert not tracker.is_down(vk)
    assert not any(tracker.is_down(other) for other in range(256))


def test_the_last_and_first_codes_are_in_range():
    tracker = KeyStateTracker()
    tracker.set(0, True)
    tracker.set(255, True)
    assert tracker.is_down(0)
    assert tracker.is_down(255)
