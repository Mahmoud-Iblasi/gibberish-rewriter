using GibberishRewriter.Core;

namespace GibberishRewriter.App.Win;

/// <summary>The Engine the hooks feed and the layout pair it was built for. AppHost swaps it when the pair changes.</summary>
internal sealed record EngineSlot(Engine Engine, LayoutPair Pair);
