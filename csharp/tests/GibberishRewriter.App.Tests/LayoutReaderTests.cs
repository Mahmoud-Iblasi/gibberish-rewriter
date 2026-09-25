using System.Text.Json.Nodes;
using GibberishRewriter.App.Win;
using GibberishRewriter.Core;

namespace GibberishRewriter.App.Tests;

public class LayoutReaderTests
{
    [LayoutPairFact]
    public void The_table_read_from_Windows_equals_the_snapshot()
    {
        var names = KeyNames.Load(SharedFiles.PathOf("keys.json"));
        var table = LayoutReader.ReadTable(names, new LayoutPair(0x04090409, 0x04012C01));
        Assert.True(JsonNode.DeepEquals(
            JsonNode.Parse(SharedFiles.ReadText("layouts/us-arabic101.json")),
            JsonNode.Parse(table.ToJson())));
    }

    [LayoutPairFact]
    public void KeyA_tells_the_snapshot_layouts_apart()
    {
        var installed = LayoutReader.InstalledWithKeyA();
        Assert.Contains((0x04090409u, "a"), installed);
        Assert.Contains((0x04012C01u, "ش"), installed);
    }
}
