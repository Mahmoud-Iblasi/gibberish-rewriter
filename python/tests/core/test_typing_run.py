import shared_files
from gibberish_rewriter.core.key_table import KeyState, KeyTable, LayoutKind
from gibberish_rewriter.core.typing_run import KeyRecord, TypingRun

TABLE = KeyTable.load(shared_files.path_of("layouts/us-arabic101.json"))


def on_arabic(key: str) -> KeyRecord:
    """A plain key press on the Arabic layout. key is the letter on the key cap."""
    return KeyRecord(
        ord(key),
        False,
        False,
        TABLE.text_of(ord(key), LayoutKind.ARABIC, KeyState.PLAIN),
        TABLE.text_of(ord(key), LayoutKind.LATIN, KeyState.PLAIN),
    )


def arabic_run(keys: str, max_length: int = 1000) -> TypingRun:
    run = TypingRun(max_length)
    for key in keys:
        run.record(1, LayoutKind.ARABIC, on_arabic(key))
    return run


def test_records_join_into_the_run_text_and_the_other_layout_text():
    run = arabic_run("HELLO")
    assert run.text == "اثممخ"
    assert run.other_text == "hello"
    assert run.layout is LayoutKind.ARABIC
    assert run.window == 1
    assert not run.sealed


def test_a_different_window_starts_a_new_run():
    run = arabic_run("HE")
    run.record(2, LayoutKind.ARABIC, on_arabic("L"))
    assert run.other_text == "l"
    assert run.window == 2


def test_a_different_layout_starts_a_new_run():
    run = arabic_run("HE")
    run.record(1, LayoutKind.LATIN, KeyRecord(ord("L"), False, False, "l", "م"))
    assert run.text == "l"
    assert run.layout is LayoutKind.LATIN


def test_the_oldest_records_are_dropped_past_the_maximum():
    assert arabic_run("HELLO", max_length=3).other_text == "llo"


def test_lowering_the_maximum_drops_the_oldest_records():
    run = arabic_run("HELLO")
    run.max_length = 2
    assert run.other_text == "lo"


def test_backspace_removes_the_last_record():
    run = arabic_run("HEL")
    run.backspace(TABLE)
    assert run.other_text == "he"


def test_backspace_on_an_empty_run_does_nothing():
    run = TypingRun(10)
    run.backspace(TABLE)
    assert run.is_empty


def test_backspace_on_lam_alef_leaves_lam():
    run = arabic_run("AB")
    assert run.text == "شلا"
    run.backspace(TABLE)
    assert run.text == "شل"
    assert run.other_text == "ag"
    assert run.records[-1].vk == ord("G")


def test_backspace_on_shifted_lam_alef_leaves_lam():
    run = TypingRun(10)
    run.record(1, LayoutKind.ARABIC, KeyRecord(ord("B"), True, False, "لآ", "B"))
    run.backspace(TABLE)
    assert run.text == "ل"
    assert run.other_text == "g"


def test_swap_after_fix_swaps_texts_moves_to_the_other_layout_and_seals():
    run = arabic_run("HELLO")
    run.swap_after_fix()
    assert run.text == "hello"
    assert run.other_text == "اثممخ"
    assert run.layout is LayoutKind.LATIN
    assert run.sealed

    run.swap_after_fix()
    assert run.text == "اثممخ"
    assert run.layout is LayoutKind.ARABIC
    assert run.sealed


def test_swap_after_fix_on_an_empty_run_does_nothing():
    run = TypingRun(10)
    run.swap_after_fix()
    assert not run.sealed
    assert run.layout is LayoutKind.LATIN


def test_the_next_record_clears_a_sealed_run():
    run = arabic_run("HI")
    run.swap_after_fix()
    run.record(1, LayoutKind.LATIN, KeyRecord(ord("A"), False, False, "a", "ش"))
    assert run.text == "a"
    assert not run.sealed


def test_backspace_clears_a_sealed_run():
    run = arabic_run("HI")
    run.swap_after_fix()
    run.backspace(TABLE)
    assert run.is_empty
    assert not run.sealed


def test_clear_empties_and_unseals():
    run = arabic_run("HI")
    run.swap_after_fix()
    run.clear()
    assert run.is_empty
    assert not run.sealed
    assert run.text == ""
