"""``--dump-layouts <file>`` writes the key table of the configured pair as JSON.

Mirrors ``csharp/src/GibberishRewriter.App/DumpLayoutsCommand.cs``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TextIO

from gibberish_rewriter.core.config import ConfigParser
from gibberish_rewriter.core.key_names import KeyNames

from gibberish_rewriter.app import app_messages
from gibberish_rewriter.win import hkl, layout_pair_resolver, layout_reader
from gibberish_rewriter.win.layout_reader import DeadKeyError


def run(shared_folder: str, config_text: str | None, output_path: str, errors: TextIO) -> int:
    """Writes the key table to output_path.

    config_text is the config to take ``layouts`` from; None means the defaults. Returns 0 when the file was
    written, otherwise 1 with a message on ``errors``.
    """
    names = KeyNames.load(os.path.join(shared_folder, "keys.json"))
    default_text = Path(os.path.join(shared_folder, "config.default.json")).read_text(encoding="utf-8")
    parser = ConfigParser(names, default_text)
    config = parser.defaults
    if config_text is not None:
        result = parser.parse(config_text)
        if result.error is not None:
            print(app_messages.config_invalid(result.error.code, result.error.message), file=errors)
            return 1
        assert result.config is not None, "parse returns a config whenever it returns no error."
        config = result.config

    resolution = layout_pair_resolver.resolve(
        config.latin_layout, config.arabic_layout, layout_reader.installed_with_key_a()
    )
    if resolution.pair is None:
        print(resolution.error, file=errors)
        return 1
    try:
        table = layout_reader.read_table(names, resolution.pair)
    except DeadKeyError as exception:
        print(app_messages.layout_has_dead_keys(hkl.format(exception.layout)), file=errors)
        return 1
    Path(output_path).write_text(table.to_json(), encoding="utf-8", newline="")
    return 0
