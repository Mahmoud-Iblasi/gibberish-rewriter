"""Paths into the repository's shared/ folder, which both apps test against."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "shared"


def path_of(relative: str) -> Path:
    return ROOT / relative


def read_text(relative: str) -> str:
    return path_of(relative).read_text(encoding="utf-8")
