using System.Text.Json;

namespace GibberishRewriter.Core.Tests;

public class ConvertVectorTests
{
    private static readonly TextConverter Converter = new(
        KeyTable.Load(SharedFiles.PathOf("layouts/us-arabic101.json")),
        WordList.Load(SharedFiles.PathOf("wordlists/english.txt")));

    public static IEnumerable<object?[]> Vectors()
    {
        using var document = JsonDocument.Parse(SharedFiles.ReadText("vectors/convert.json"));
        var rows = new List<object?[]>();
        foreach (var vector in document.RootElement.EnumerateArray())
        {
            var expect = vector.GetProperty("expect");
            var none = expect.ValueKind == JsonValueKind.Null;
            rows.Add(
            [
                vector.GetProperty("name").GetString(),
                vector.GetProperty("text").GetString(),
                none ? null : expect.GetProperty("text").GetString(),
                none ? null : expect.GetProperty("target").GetString(),
            ]);
        }
        return rows;
    }

    [Theory]
    [MemberData(nameof(Vectors))]
    public void Convert_vector(string name, string text, string? expectedText, string? expectedTarget)
    {
        var conversion = Converter.Convert(text);
        if (expectedText is null)
        {
            Assert.True(conversion is null, $"{name}: expected no conversion, got '{conversion?.Text}'");
            return;
        }
        Assert.NotNull(conversion);
        Assert.Equal(expectedText, conversion.Text);
        Assert.Equal(LayoutKinds.Parse(expectedTarget!), conversion.Target);
    }
}
