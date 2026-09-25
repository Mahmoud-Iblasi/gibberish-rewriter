import pytest

from gibberish_rewriter.core.engine import KeyEvent
from gibberish_rewriter.core.key_names import VK_CAPS_LOCK, HoldKeys
from gibberish_rewriter.core.key_table import LayoutKind
from harness.vector_runner import VectorRunner, load_vectors, vector_named

FILE = "vectors/chords.json"
VECTORS = load_vectors(FILE)


@pytest.mark.parametrize("vector", VECTORS, ids=[vector["name"] for vector in VECTORS])
def test_chord_vector(vector):
    runner = VectorRunner(vector)
    runner.run(vector["events"])
    assert runner.decisions == vector["expect"]


def test_keys_the_app_injected_always_pass_untouched():
    runner = VectorRunner(vector_named(FILE, "CapsLock tap toggles on release"))
    decision = runner.engine.on_key(
        KeyEvent(VK_CAPS_LOCK, True, True, False, HoldKeys.NONE, 1, LayoutKind.LATIN)
    )
    assert not decision.swallow
    assert list(decision.send_keys) == []
