namespace GibberishRewriter.App.Tests;

public class AppLogTests
{
    [Fact]
    public void Write_appends_timestamped_lines()
    {
        using var folder = new TempFolder();
        var log = new AppLog(folder.PathOf("logs/csharp.log"));

        log.Write("Starting");
        log.Write("Ran FixTyped");

        var lines = File.ReadAllLines(folder.PathOf("logs/csharp.log"));
        Assert.Equal(2, lines.Length);
        Assert.Matches(@"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} Ran FixTyped$", lines[1]);
    }

    [Fact]
    public void A_full_log_rolls_over_to_one_old_file()
    {
        using var folder = new TempFolder();
        var path = folder.PathOf("csharp.log");
        var log = new AppLog(path, maxBytes: 200);

        for (var i = 0; i < 20; i++)
        {
            log.Write($"line {i:D2} " + new string('x', 20));
        }

        Assert.True(File.Exists(path + ".1"));
        Assert.False(File.Exists(path + ".2"));
        Assert.True(new FileInfo(path).Length <= 200);
        Assert.True(new FileInfo(path + ".1").Length <= 200);
        Assert.EndsWith("line 19 " + new string('x', 20), File.ReadAllLines(path)[^1]);
    }
}

public class ConfigFileTests
{
    [Fact]
    public void EnsureExists_writes_the_defaults_only_when_there_is_no_file()
    {
        using var folder = new TempFolder();
        var file = new ConfigFile(folder.PathOf("GibberishRewriter/config.json"));

        file.EnsureExists("{ \"enabled\": true }");
        file.EnsureExists("{ \"enabled\": false }");

        Assert.Equal("{ \"enabled\": true }", File.ReadAllText(file.FilePath));
    }

    [Fact]
    public void ReadIfChanged_returns_the_text_first_and_then_only_after_a_change()
    {
        using var folder = new TempFolder();
        var file = new ConfigFile(folder.PathOf("config.json"));
        File.WriteAllText(file.FilePath, "{}");

        Assert.Equal("{}", file.ReadIfChanged());
        Assert.Null(file.ReadIfChanged());

        File.WriteAllText(file.FilePath, "{ \"enabled\": false }");
        File.SetLastWriteTimeUtc(file.FilePath, DateTime.UtcNow.AddSeconds(5));
        Assert.Equal("{ \"enabled\": false }", file.ReadIfChanged());
    }

    [Fact]
    public void ReadIfChanged_treats_a_missing_file_as_unchanged()
    {
        using var folder = new TempFolder();
        Assert.Null(new ConfigFile(folder.PathOf("config.json")).ReadIfChanged());
    }

    [Fact]
    public void ReadText_drops_a_UTF8_byte_order_mark()
    {
        using var folder = new TempFolder();
        var path = folder.PathOf("config.json");
        File.WriteAllBytes(path, [0xEF, 0xBB, 0xBF, (byte)'{', (byte)'}']);
        Assert.Equal("{}", ConfigFile.ReadText(path));
    }
}
