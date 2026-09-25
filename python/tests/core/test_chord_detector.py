import pytest

import shared_files
from gibberish_rewriter.core.chord_detector import PASS, SWALLOW_KEY, ChordAction, ChordDecision, ChordDetector
from gibberish_rewriter.core.config import Chord
from gibberish_rewriter.core.key_names import HoldKeys, KeyNames

TAB = 0x09
BACKQUOTE = 0xC0
CAPS_LOCK = 0x14
SHIFT_LEFT = 0xA0
KEY_A = 0x41
F9 = 0x78
F10 = 0x79

NAMES = KeyNames.load(shared_files.path_of("keys.json"))


def detector() -> ChordDetector:
    return ChordDetector(
        NAMES,
        Chord(HoldKeys.SHIFT | HoldKeys.CAPS_LOCK, TAB),
        Chord(HoldKeys.SHIFT | HoldKeys.CAPS_LOCK, BACKQUOTE),
    )


def test_chord_fires_on_trigger_down_and_swallows_the_trigger_repeats_and_up():
    detect = detector()
    assert detect.on_key(SHIFT_LEFT, True, HoldKeys.NONE) == PASS
    assert detect.on_key(CAPS_LOCK, True, HoldKeys.SHIFT) == SWALLOW_KEY
    assert detect.on_key(TAB, True, HoldKeys.SHIFT) == ChordDecision(True, ChordAction.FIX_TYPED)
    assert detect.on_key(TAB, True, HoldKeys.SHIFT) == SWALLOW_KEY
    assert detect.on_key(TAB, False, HoldKeys.SHIFT) == SWALLOW_KEY
    assert detect.on_key(CAPS_LOCK, False, HoldKeys.SHIFT) == SWALLOW_KEY
    assert detect.on_key(SHIFT_LEFT, False, HoldKeys.SHIFT) == PASS


def test_hold_keys_can_be_pressed_in_any_order():
    detect = detector()
    assert detect.on_key(CAPS_LOCK, True, HoldKeys.NONE) == SWALLOW_KEY
    assert detect.on_key(SHIFT_LEFT, True, HoldKeys.NONE) == PASS
    assert detect.on_key(BACKQUOTE, True, HoldKeys.SHIFT).fired is ChordAction.FIX_SELECTION


def test_a_caps_lock_tap_is_swallowed_and_replayed_on_release():
    detect = detector()
    assert detect.on_key(CAPS_LOCK, True, HoldKeys.NONE) == SWALLOW_KEY
    assert detect.on_key(CAPS_LOCK, True, HoldKeys.NONE) == SWALLOW_KEY
    assert detect.on_key(CAPS_LOCK, False, HoldKeys.NONE) == ChordDecision(
        True, replay_caps_lock=True, caps_lock_toggled=True
    )
    assert not detect.caps_lock_down


def test_caps_lock_held_while_typing_is_still_replayed():
    detect = detector()
    detect.on_key(CAPS_LOCK, True, HoldKeys.NONE)
    assert detect.caps_lock_down
    assert detect.on_key(KEY_A, True, HoldKeys.NONE) == PASS
    assert detect.on_key(KEY_A, False, HoldKeys.NONE) == PASS
    assert detect.on_key(CAPS_LOCK, False, HoldKeys.NONE).replay_caps_lock


def test_a_caps_lock_up_without_a_down_is_swallowed_without_a_replay():
    assert detector().on_key(CAPS_LOCK, False, HoldKeys.NONE) == SWALLOW_KEY


def test_an_extra_held_modifier_stops_the_chord():
    detect = detector()
    detect.on_key(CAPS_LOCK, True, HoldKeys.NONE)
    assert detect.on_key(TAB, True, HoldKeys.SHIFT | HoldKeys.CTRL) == PASS


def test_a_missing_hold_key_stops_the_chord():
    detect = detector()
    assert detect.on_key(TAB, True, HoldKeys.SHIFT) == PASS
    assert detect.on_key(TAB, False, HoldKeys.SHIFT) == PASS
    detect.on_key(CAPS_LOCK, True, HoldKeys.NONE)
    assert detect.on_key(TAB, True, HoldKeys.NONE) == PASS


def test_both_triggers_held_at_once_each_keep_their_key_up_swallowed():
    detect = detector()
    detect.on_key(SHIFT_LEFT, True, HoldKeys.NONE)
    detect.on_key(CAPS_LOCK, True, HoldKeys.SHIFT)
    assert detect.on_key(TAB, True, HoldKeys.SHIFT).fired is ChordAction.FIX_TYPED
    assert detect.on_key(BACKQUOTE, True, HoldKeys.SHIFT).fired is ChordAction.FIX_SELECTION
    assert detect.on_key(TAB, False, HoldKeys.SHIFT) == SWALLOW_KEY
    assert detect.on_key(BACKQUOTE, False, HoldKeys.SHIFT) == SWALLOW_KEY


def test_modifier_keys_always_pass():
    detect = detector()
    for vk in (0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C, 0x90, 0x91, 0x10):
        assert detect.on_key(vk, True, HoldKeys.NONE) == PASS
        assert detect.on_key(vk, False, HoldKeys.NONE) == PASS


def test_caps_lock_passes_and_reports_toggles_when_no_chord_holds_it():
    detect = ChordDetector(
        NAMES, Chord(HoldKeys.CTRL | HoldKeys.ALT, F9), Chord(HoldKeys.CTRL | HoldKeys.ALT, F10)
    )
    assert detect.on_key(CAPS_LOCK, True, HoldKeys.NONE) == ChordDecision(False, caps_lock_toggled=True)
    assert detect.on_key(CAPS_LOCK, True, HoldKeys.NONE) == PASS
    assert detect.on_key(CAPS_LOCK, False, HoldKeys.NONE) == PASS


def test_a_held_caps_lock_counts_as_an_extra_key_for_chords_without_it():
    detect = ChordDetector(NAMES, Chord(HoldKeys.CTRL, F9), Chord(HoldKeys.CTRL, F10))
    detect.on_key(CAPS_LOCK, True, HoldKeys.NONE)
    assert detect.on_key(F9, True, HoldKeys.CTRL) == PASS


@pytest.mark.parametrize(
    ("hold", "expected"),
    [
        (HoldKeys.CTRL | HoldKeys.ALT, True),
        (HoldKeys.WIN, True),
        (HoldKeys.CTRL | HoldKeys.SHIFT, False),
    ],
)
def test_chords_holding_alt_or_win_ask_for_the_mask_key(hold: HoldKeys, expected: bool):
    detect = ChordDetector(NAMES, Chord(hold, F9), Chord(hold, F10))
    decision = detect.on_key(F9, True, hold)
    assert decision.fired is ChordAction.FIX_TYPED
    assert decision.send_mask_key == expected


def test_set_chords_forgets_a_half_pressed_chord():
    detect = detector()
    detect.on_key(CAPS_LOCK, True, HoldKeys.NONE)
    detect.set_chords(
        Chord(HoldKeys.SHIFT | HoldKeys.CAPS_LOCK, TAB), Chord(HoldKeys.SHIFT | HoldKeys.CAPS_LOCK, BACKQUOTE)
    )
    assert not detect.caps_lock_down
    assert detect.on_key(CAPS_LOCK, False, HoldKeys.NONE) == SWALLOW_KEY
