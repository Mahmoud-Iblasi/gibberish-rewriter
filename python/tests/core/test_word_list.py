import pytest

import shared_files
from gibberish_rewriter.core.word_list import WordList

WORDS = WordList.load(shared_files.path_of("wordlists/english.txt"))


@pytest.mark.parametrize("word", ["right", "about", "hello", "there", "don't"])
def test_shared_list_has_common_words(word):
    assert WORDS.contains(word)


@pytest.mark.parametrize("word", ["ribt", "Right", ""])
def test_shared_list_rejects_non_words_and_capitals(word):
    assert not WORDS.contains(word)


def test_shared_list_is_lowercase_sorted_unique_and_large():
    lines = shared_files.read_text("wordlists/english.txt").splitlines()
    assert len(lines) > 50_000, f"only {len(lines)} words"
    for index, line in enumerate(lines):
        assert line.lower() == line
        if index > 0:
            assert lines[index - 1] < line, f"not sorted at line {index + 1}: {line}"


def test_licence_notice_is_saved_next_to_the_list():
    assert "Kevin Atkinson" in shared_files.read_text("wordlists/ESDB-COPYRIGHT.txt")


def test_from_words_trims_and_skips_blank_lines():
    words = WordList.from_words(["cat", "  dog ", "", "   "])
    assert words.count == 2
    assert words.contains("dog")
