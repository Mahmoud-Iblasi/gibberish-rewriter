"""Mirrors csharp/tests/GibberishRewriter.App.Tests/DumpLayoutsCommandTests.cs.

The dump itself reads the installed layouts, so it runs only with GIBBERISH_INTEGRATION=1 and only where English
(US) 04090409 and Arabic (101) 04012C01 are installed, exactly as the C# [LayoutPairFact] does.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest
import shared_files

from gibberish_rewriter.app import dump_layouts_command
from gibberish_rewriter.win import layout_reader

INTEGRATION_VARIABLE = "GIBBERISH_INTEGRATION"
ENGLISH_US = 0x04090409
ARABIC_101 = 0x04012C01


def _layout_pair_reason() -> str | None:
    if os.environ.get(INTEGRATION_VARIABLE) != "1":
        return f"Windows integration test. Set {INTEGRATION_VARIABLE}=1 to run it."
    installed = layout_reader.installed_layouts()
    if ENGLISH_US not in installed or ARABIC_101 not in installed:
        return "English (US) 04090409 and Arabic (101) 04012C01 aren't both installed."
    return None


_REASON = _layout_pair_reason()
layout_pair = pytest.mark.skipif(_REASON is not None, reason=_REASON or "")


@layout_pair
def test_the_dump_equals_the_snapshot(tmp_path):
    output = tmp_path / "dump.json"
    errors = io.StringIO()

    exit_code = dump_layouts_command.run(
        str(shared_files.ROOT),
        '{ "layouts": { "latin": "04090409", "arabic": "04012C01" } }',
        str(output),
        errors,
    )

    assert errors.getvalue() == ""
    assert exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8")) == json.loads(
        shared_files.read_text("layouts/us-arabic101.json")
    )


def test_an_invalid_config_is_reported_and_nothing_is_written(tmp_path):
    output = tmp_path / "dump.json"
    errors = io.StringIO()

    assert (
        dump_layouts_command.run(
            str(shared_files.ROOT), '{ "layouts": { "latin": "xyz" } }', str(output), errors
        )
        == 1
    )

    assert "layout.invalid" in errors.getvalue()
    assert not Path(output).exists()
