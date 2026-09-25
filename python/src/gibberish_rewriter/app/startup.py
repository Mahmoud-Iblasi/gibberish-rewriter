"""Telling a file in ``shared/`` the app can't read apart from a bug in the app.

Mirrors ``csharp/src/GibberishRewriter.App/Startup.cs``. The C# tests three exception types; Python's exceptions
do not line up one for one, so the mapping is spelled out below and the tests check both sides of it.
"""

from __future__ import annotations

_A_MISSING_FILE: tuple[type[BaseException], ...] = (OSError, ValueError, KeyError)
"""``OSError`` is C#'s ``IOException`` and ``UnauthorizedAccessException``: a missing folder, a missing file, a
locked one, and Pillow's ``UnidentifiedImageError`` for a file that is not an icon. ``ValueError`` and ``KeyError``
are its ``ArgumentException``: the file is there but is not what it should be, which is what the Core raises for a
malformed ``keys.json`` (``KeyError`` for an unknown hold key, ``ValueError`` for a bad ``tableKeys`` entry) and
what ``json.JSONDecodeError`` and ``UnicodeDecodeError`` are subclasses of."""

_A_BUG_IN_THE_APP: tuple[type[BaseException], ...] = (TypeError, IndexError)
"""C# keeps ``ArgumentNullException`` and ``ArgumentOutOfRangeException`` out of the guard, because a bad argument
from our own code is a bug, not a missing file. These are their Python counterparts, and ``TypeError`` is also what
calling something with the wrong arguments raises."""


def is_shared_file_problem(exception: BaseException) -> bool:
    """True for what reading ``shared/`` raises, and false for what a bug in this app raises."""
    if isinstance(exception, _A_BUG_IN_THE_APP):
        return False
    return isinstance(exception, _A_MISSING_FILE)
