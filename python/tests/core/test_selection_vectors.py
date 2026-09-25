import pytest

from harness.vector_runner import VectorRunner, load_vectors

FILE = "vectors/selection.json"
VECTORS = load_vectors(FILE)


@pytest.mark.parametrize("vector", VECTORS, ids=[vector["name"] for vector in VECTORS])
def test_selection_vector(vector):
    runner = VectorRunner(vector)
    runner.run(vector["events"])
    assert runner.platform.calls == VectorRunner.expected_calls(vector)
