import pytest

import shared_files
from gibberish_rewriter.core.key_table import KeyTable, LayoutKind
from gibberish_rewriter.core.text_converter import Conversion, TextConverter
from gibberish_rewriter.core.word_list import WordList

TABLE = KeyTable.load(shared_files.path_of("layouts/us-arabic101.json"))


def converter(*words: str) -> TextConverter:
    return TextConverter(TABLE, WordList.from_words(words))


@pytest.mark.parametrize("text", ["", "123 !", "ََ"])
def test_text_without_letters_is_not_converted(text):
    assert converter().convert(text) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("lvpfh", "مرحبا"),
        ("LVPFH", "مرحبا"),
        ("Lvpfh", "/رحبا"),
        ("A", "ِ"),
        (";dt phg;?", "كيف حالك؟"),
        (",hkj", "وانت"),
        ("hello\nthere", "اثممخ\nفاثقث"),
        ("a\U0001F600", "ش\U0001F600"),
        ("ََa", "ََش"),
    ],
)
def test_latin_text_is_converted_to_the_arabic_layout(text, expected):
    assert converter().convert(text) == Conversion(expected, LayoutKind.ARABIC)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("اثممخ", "hello"),
        ("اثممخ فاثقث اخص شقث غخع", "hello there how are you"),
        ("Hello اخص شقث غخع", "Hello how are you"),
        ("كيف حالك؟", ";dt phg;?"),
        ("ي]", "d]"),
        ("ــa", "JJa"),
        ("شلاخعف", "about"),
    ],
)
def test_arabic_text_is_converted_to_the_latin_layout(text, expected):
    assert converter().convert(text) == Conversion(expected, LayoutKind.LATIN)


@pytest.mark.parametrize(
    ("text", "expected", "target"),
    [("ab اب", "ab hf", LayoutKind.LATIN), ("اب ab", "اب شلا", LayoutKind.ARABIC)],
)
def test_a_tie_uses_the_script_of_the_last_letter(text, expected, target):
    assert converter().convert(text) == Conversion(expected, target)


@pytest.mark.parametrize(("text", "expected"), [("قهلاف", "right"), ("قهلاف.", "right."), ("شلاخعف", "about")])
def test_lam_alef_is_resolved_with_the_word_list(text, expected):
    assert converter("right", "about").convert(text).text == expected


def test_words_not_in_the_list_read_every_sequence_as_one_key():
    assert converter().convert("قهلاف").text == "ribt"


def test_combinations_are_tried_in_binary_counting_order_with_the_leftmost_sequence_most_significant():
    assert converter("ghb", "bgh").convert("لالا").text == "bgh"


def test_each_word_is_resolved_on_its_own():
    assert converter("right").convert("قهلاف لا").text == "right b"


def test_six_sequences_are_still_checked():
    assert converter("ghghghghghgh").convert("لالالالالالا").text == "ghghghghghgh"


def test_words_with_more_than_six_sequences_are_not_checked():
    assert converter("ghghghghghghgh").convert("لالالالالالالا").text == "bbbbbbb"


@pytest.mark.parametrize(("text", "expected"), [("لآ", "gN"), ("لأ", "gH"), ("لإ", "gY")])
def test_every_lam_alef_form_has_a_two_key_reading(text, expected):
    assert converter(expected.lower()).convert(text).text == expected
