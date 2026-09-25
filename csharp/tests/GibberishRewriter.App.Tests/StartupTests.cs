using GibberishRewriter.App;
using GibberishRewriter.Core;

namespace GibberishRewriter.App.Tests;

/// <summary>The start notification, and a shared file that can't be read.</summary>
public class StartupTests
{
    private static readonly KeyNames Names = KeyNames.Load(SharedFiles.PathOf("keys.json"));

    private static string StartedText()
    {
        var parser = new ConfigParser(Names, SharedFiles.ReadText("config.default.json"));
        var config = parser.Defaults;
        return AppMessages.Started("04090409", "04012C01", config.FixTyped.Format(Names), config.FixSelection.Format(Names));
    }

    [Fact]
    public void The_start_notification_names_both_layouts()
    {
        var text = StartedText();
        Assert.Contains("04090409", text);
        Assert.Contains("04012C01", text);
    }

    [Fact]
    public void The_start_notification_names_both_hotkeys_as_the_config_spells_them()
    {
        var text = StartedText();
        Assert.Contains("Shift+CapsLock+Tab", text);
        Assert.Contains("Shift+CapsLock+Backquote", text);
    }

    /// <summary>A balloon tip is cut off past 255 characters (Tray.MaxNotificationLength).</summary>
    [Fact]
    public void The_start_notification_fits_in_a_balloon() => Assert.True(StartedText().Length <= 255);

    [Fact]
    public void The_unreadable_message_names_the_folder_and_the_error()
    {
        var text = AppMessages.SharedFilesUnreadable(@"C:\dist\shared", "Could not find a part of the path.");
        Assert.Contains(@"C:\dist\shared", text);
        Assert.Contains("Could not find a part of the path.", text);
        Assert.Contains("shared", text);
    }

    [Theory]
    [InlineData(typeof(DirectoryNotFoundException))]
    [InlineData(typeof(FileNotFoundException))]
    [InlineData(typeof(IOException))]
    [InlineData(typeof(UnauthorizedAccessException))]
    [InlineData(typeof(ArgumentException))]
    public void A_shared_file_problem_is_recognized(Type exceptionType) =>
        Assert.True(Startup.IsSharedFileProblem((Exception)Activator.CreateInstance(exceptionType)!));

    [Theory]
    [InlineData(typeof(InvalidOperationException))]
    [InlineData(typeof(ArgumentNullException))]
    [InlineData(typeof(ArgumentOutOfRangeException))]
    public void A_bug_in_the_app_is_not_treated_as_a_shared_file_problem(Type exceptionType) =>
        Assert.False(Startup.IsSharedFileProblem((Exception)Activator.CreateInstance(exceptionType)!));

    /// <summary>The real failure: the published folder was missing shared\icons, and the app exited silently.</summary>
    [Fact]
    public void A_missing_shared_folder_raises_something_the_guard_catches()
    {
        var missing = Path.Combine(Path.GetTempPath(), "gibberish-rewriter-no-such-folder", "keys.json");
        var exception = Record.Exception(() => KeyNames.Load(missing));
        Assert.NotNull(exception);
        Assert.True(Startup.IsSharedFileProblem(exception));
    }
}
