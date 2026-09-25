using GibberishRewriter.App.Win;

namespace GibberishRewriter.App.Tests;

public class ForegroundTests
{
    [Theory]
    [InlineData("ConsoleWindowClass", true)]
    [InlineData("CASCADIA_HOSTING_WINDOW_CLASS", true)]
    [InlineData("Chrome_WidgetWin_1", false)]
    [InlineData("Notepad", false)]
    [InlineData("consolewindowclass", false)]
    public void IsConsoleClass_matches_the_two_console_classes_exactly(string className, bool expected) =>
        Assert.Equal(expected, Foreground.IsConsoleClass(className));

    [Fact]
    public void No_window_is_not_blocked_by_elevation() =>
        Assert.False(Foreground.IsBlockedByElevation(IntPtr.Zero));
}
