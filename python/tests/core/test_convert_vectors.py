import json

import pytest

import shared_files
from gibberish_rewriter.core.key_table import KeyTable, LayoutKind
from gibberish_rewriter.core.text_converter import TextConverter
from gibberish_rewriter.core.word_list import WordList

CONVERTER = TextConverter(
    KeyTable.load(shared_files.path_of("layouts/us-arabic101.json")),
    WordList.load(shared_files.path_of("wordlists/english.txt")),
)
VECTORS = json.loads(shared_files.read_text("vectors/convert.json"))


@pytest.mark.parametrize("vector", VECTORS, ids=[vector["name"] for vector in VECTORS])
def test_convert_vector(vector):
    conversion = CONVERTER.convert(vector["text"])
    expect = vector["expect"]
    if expect is None:
        assert conversion is None, f"expected no conversion, got {conversion.text!r}"
        return
    assert conversion is not None
    assert conversion.text == expect["text"]
    assert conversion.target is LayoutKind.parse(expect["target"])
