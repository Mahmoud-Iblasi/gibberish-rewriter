using System.Text.Json;

namespace GibberishRewriter.Core.Tests;

public class ConfigParserTests
{
    private static readonly KeyNames Names = KeyNames.Load(SharedFiles.PathOf("keys.json"));
    private static readonly ConfigParser Parser = new(Names, SharedFiles.ReadText("config.default.json"));
    private static readonly Dictionary<string, JsonElement> VectorsByName = LoadVectors();

    private static Dictionary<string, JsonElement> LoadVectors()
    {
        using var document = JsonDocument.Parse(SharedFiles.ReadText("vectors/config.json"));
        return document.RootElement.EnumerateArray()
            .ToDictionary(vector => vector.GetProperty("name").GetString()!, vector => vector.Clone());
    }

    public static IEnumerable<object[]> VectorNames() => LoadVectors().Keys.Select(name => new object[] { name });

    [Theory]
    [MemberData(nameof(VectorNames))]
    public void Config_vector(string name)
    {
        var vector = VectorsByName[name];
        var result = Parser.Parse(vector.GetProperty("json").GetString()!);

        if (vector.TryGetProperty("error", out var expectedError))
        {
            Assert.Null(result.Config);
            Assert.Equal(expectedError.GetString(), result.Error?.Code);
            return;
        }

        Assert.Null(result.Error);
        var config = result.Config!;
        foreach (var field in vector.GetProperty("expect").EnumerateObject())
        {
            object actual = field.Name switch
            {
                "enabled" => config.Enabled,
                "fixTyped" => config.FixTyped.Format(Names),
                "fixSelection" => config.FixSelection.Format(Names),
                "switchLayoutAfterFix" => config.SwitchLayoutAfterFix,
                "latinLayout" => config.LatinLayout,
                "arabicLayout" => config.ArabicLayout,
                "maxRunLength" => config.MaxRunLength,
                "clipboardTimeoutMs" => config.ClipboardTimeoutMs,
                "pasteRestoreDelayMs" => config.PasteRestoreDelayMs,
                "releaseTimeoutMs" => config.ReleaseTimeoutMs,
                _ => throw new InvalidOperationException($"Unknown expect field '{field.Name}' in '{name}'."),
            };
            object expected = field.Value.ValueKind switch
            {
                JsonValueKind.True => true,
                JsonValueKind.False => false,
                JsonValueKind.Number => field.Value.GetInt32(),
                _ => field.Value.GetString()!,
            };
            Assert.Equal(expected, actual);
        }
    }

    [Fact]
    public void Defaults_come_from_config_default_json()
    {
        Assert.True(Parser.Defaults.Enabled);
        Assert.Equal("Shift+CapsLock+Tab", Parser.Defaults.FixTyped.Format(Names));
        Assert.Equal("Shift+CapsLock+Backquote", Parser.Defaults.FixSelection.Format(Names));
        Assert.Equal(1000, Parser.Defaults.MaxRunLength);
    }

    [Fact]
    public void An_incomplete_default_file_is_rejected() =>
        Assert.Throws<FormatException>(() => new ConfigParser(Names, "{}"));

    [Fact]
    public void Error_messages_name_the_field() =>
        Assert.Contains("maxRunLength", Parser.Parse("""{ "maxRunLength": 9 }""").Error!.Message);

    [Fact]
    public void Chord_Format_writes_hold_keys_in_canonical_order() =>
        Assert.Equal(
            "Shift+Win+CapsLock+Tab",
            new Chord(HoldKeys.CapsLock | HoldKeys.Win | HoldKeys.Shift, 0x09).Format(Names));

    [Fact]
    public void ParseChord_accepts_a_backtick_and_mixed_case()
    {
        var (chord, error) = Parser.ParseChord(" capslock + SHIFT + ` ", "test");
        Assert.Null(error);
        Assert.Equal(new Chord(HoldKeys.Shift | HoldKeys.CapsLock, 0xC0), chord);
    }
}
