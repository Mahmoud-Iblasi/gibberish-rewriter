"""The Engine the hooks feed and the layout pair it was built for. AppHost swaps it when the pair changes.

Mirrors ``csharp/src/GibberishRewriter.App/Win/EngineSlot.cs``.
"""

from __future__ import annotations

from dataclasses import dataclass

from gibberish_rewriter.core.engine import Engine

from gibberish_rewriter.win.hkl import LayoutPair


@dataclass(frozen=True)
class EngineSlot:
    """One Engine and its pair, read as a whole so the two can never disagree."""

    engine: Engine
    pair: LayoutPair
