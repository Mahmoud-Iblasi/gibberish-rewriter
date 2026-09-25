using GibberishRewriter.App.Win;

namespace GibberishRewriter.App.Tests;

public class AutostartTests
{
    private const string Exe = @"C:\Users\me\gibberish rewriter\GibberishRewriter.exe";

    [Fact]
    public void CommandFor_quotes_the_path() =>
        Assert.Equal("\"" + Exe + "\"", Autostart.CommandFor(Exe));

    [Theory]
    [InlineData("\"C:\\Users\\me\\gibberish rewriter\\GibberishRewriter.exe\"", true)]
    [InlineData("C:\\USERS\\ME\\gibberish rewriter\\GibberishRewriter.exe", true)]
    [InlineData("\"C:\\Users\\me\\gibberish rewriter\\python\\.venv\\Scripts\\pythonw.exe\" -m gibberish_rewriter", false)]
    [InlineData(null, false)]
    public void PointsAt_recognizes_only_this_exe(string? command, bool expected) =>
        Assert.Equal(expected, Autostart.PointsAt(command, Exe));

    /// <summary>The Python app's Run value carries arguments, so only the executable can be compared.</summary>
    [Theory]
    [InlineData("\"C:\\py\\pythonw.exe\" -m gibberish_rewriter", true)]
    [InlineData("  \"C:\\py\\pythonw.exe\"  -m gibberish_rewriter  ", true)]
    [InlineData("\"C:\\py\\pythonw.exe\"", true)]
    [InlineData("C:\\py\\pythonw.exe -m gibberish_rewriter", true)]
    [InlineData("\"C:\\py\\pythonw.exe", true)]
    [InlineData("\"C:\\py\\other.exe\" -m gibberish_rewriter", false)]
    public void PointsAt_compares_the_executable_of_a_command_with_arguments(string command, bool expected) =>
        Assert.Equal(expected, Autostart.PointsAt(command, @"C:\py\pythonw.exe"));
}

public class SingleInstanceTests
{
    [Fact]
    public void Both_apps_use_the_same_mutex_name() =>
        Assert.Equal(@"Local\GibberishRewriter.SingleInstance", SingleInstance.MutexName);

    [Fact]
    public void A_second_copy_is_refused_until_the_first_exits()
    {
        var name = @"Local\GibberishRewriter.Test." + Guid.NewGuid().ToString("N");
        using (var first = SingleInstance.TryAcquire(name))
        {
            Assert.NotNull(first);
            Assert.Null(SingleInstance.TryAcquire(name));
        }
        using var again = SingleInstance.TryAcquire(name);
        Assert.NotNull(again);
    }
}
