"""Mirrors csharp/tests/GibberishRewriter.App.Tests/AppFileTests.cs, plus the byte order mark the C# only has to
strip because the Core's parser refuses one."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

import shared_files
from gibberish_rewriter.core.config import ConfigParser
from gibberish_rewriter.core.key_names import KeyNames

from gibberish_rewriter.app.app_log import AppLog
from gibberish_rewriter.app.config_file import ConfigFile


def test_write_appends_timestamped_lines(tmp_path):
    path = tmp_path / "logs" / "python.log"
    log = AppLog(str(path))

    log.write("Starting")
    log.write("Ran FixTyped")

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} Ran FixTyped", lines[1])


def test_lines_end_the_way_the_csharp_log_ends_them(tmp_path):
    """Both apps write into %APPDATA%\\GibberishRewriter\\logs; C# appends "\\n", never "\\r\\n"."""
    path = tmp_path / "python.log"
    AppLog(str(path)).write("Starting")
    assert path.read_bytes().endswith(b"Starting\n")
    assert b"\r" not in path.read_bytes()


def test_a_full_log_rolls_over_to_one_old_file(tmp_path):
    path = tmp_path / "python.log"
    log = AppLog(str(path), max_bytes=200)

    for index in range(20):
        log.write(f"line {index:02d} " + "x" * 20)

    assert (tmp_path / "python.log.1").exists()
    assert not (tmp_path / "python.log.2").exists()
    assert path.stat().st_size <= 200
    assert (tmp_path / "python.log.1").stat().st_size <= 200
    assert path.read_text(encoding="utf-8").splitlines()[-1].endswith("line 19 " + "x" * 20)


def test_a_log_that_cannot_be_written_is_skipped(tmp_path):
    """A log is never allowed to take the app down. A folder where the file should be is unwritable."""
    path = tmp_path / "python.log"
    path.mkdir()
    AppLog(str(path)).write("Starting")


def test_ensure_exists_writes_the_defaults_only_when_there_is_no_file(tmp_path):
    file = ConfigFile(str(tmp_path / "GibberishRewriter" / "config.json"))

    file.ensure_exists('{ "enabled": true }')
    file.ensure_exists('{ "enabled": false }')

    assert Path(file.file_path).read_text(encoding="utf-8") == '{ "enabled": true }'


def test_read_if_changed_returns_the_text_first_and_then_only_after_a_change(tmp_path):
    file = ConfigFile(str(tmp_path / "config.json"))
    Path(file.file_path).write_text("{}", encoding="utf-8", newline="")

    assert file.read_if_changed() == "{}"
    assert file.read_if_changed() is None

    Path(file.file_path).write_text('{ "enabled": false }', encoding="utf-8", newline="")
    ahead = time.time() + 5
    os.utime(file.file_path, (ahead, ahead))
    assert file.read_if_changed() == '{ "enabled": false }'


def test_read_if_changed_treats_a_missing_file_as_unchanged(tmp_path):
    assert ConfigFile(str(tmp_path / "config.json")).read_if_changed() is None


def test_read_text_drops_a_utf8_byte_order_mark(tmp_path):
    path = tmp_path / "config.json"
    path.write_bytes(b"\xef\xbb\xbf{}")
    assert ConfigFile.read_text(str(path)) == "{}"


def test_a_config_saved_by_notepad_parses_only_because_the_mark_is_stripped(tmp_path):
    """A byte order mark at the start of the config is ignored, and the Core's parser deliberately does not strip one, so
    every Notepad-saved config depends on ConfigFile.read_text doing it."""
    path = tmp_path / "config.json"
    path.write_bytes(b"\xef\xbb\xbf" + b'{ "enabled": false }')
    parser = ConfigParser(
        KeyNames.load(shared_files.path_of("keys.json")), shared_files.read_text("config.default.json")
    )

    assert parser.parse(path.read_text(encoding="utf-8")).error is not None

    result = parser.parse(ConfigFile.read_text(str(path)))
    assert result.error is None
    assert result.config is not None
    assert result.config.enabled is False


def test_the_app_data_folder_is_the_one_both_apps_use():
    """One config file for both apps, and the logs beside it."""
    assert ConfigFile.app_data_folder().endswith(os.path.join("Roaming", "GibberishRewriter"))
    assert ConfigFile.default_path().endswith(os.path.join("GibberishRewriter", "config.json"))
    assert AppLog.default_path().endswith(os.path.join("GibberishRewriter", "logs", "python.log"))
