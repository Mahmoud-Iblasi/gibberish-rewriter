using System.Text.Json.Nodes;

namespace GibberishRewriter.App.Tests;

public class DumpLayoutsCommandTests
{
    [LayoutPairFact]
    public void The_dump_equals_the_snapshot()
    {
        using var folder = new TempFolder();
        var output = folder.PathOf("dump.json");
        var errors = new StringWriter();

        var exitCode = DumpLayoutsCommand.Run(
            SharedFiles.Root, """{ "layouts": { "latin": "04090409", "arabic": "04012C01" } }""", output, errors);

        Assert.Equal("", errors.ToString());
        Assert.Equal(0, exitCode);
        Assert.True(JsonNode.DeepEquals(
            JsonNode.Parse(SharedFiles.ReadText("layouts/us-arabic101.json")),
            JsonNode.Parse(File.ReadAllText(output))));
    }

    [Fact]
    public void An_invalid_config_is_reported_and_nothing_is_written()
    {
        using var folder = new TempFolder();
        var output = folder.PathOf("dump.json");
        var errors = new StringWriter();

        Assert.Equal(1, DumpLayoutsCommand.Run(SharedFiles.Root, """{ "layouts": { "latin": "xyz" } }""", output, errors));

        Assert.Contains("layout.invalid", errors.ToString());
        Assert.False(File.Exists(output));
    }
}
