using GibberishRewriter.App.Win;

namespace GibberishRewriter.App.Tests;

public class LayoutSwitcherTests
{
    [Theory]
    [InlineData(0x04090409u, 0x04012C01u, 2, true)]
    [InlineData(0x04090409u, 0x04012C01u, 3, false)]
    [InlineData(0x04012C01u, 0x04012C01u, 2, false)]
    public void Win_Space_only_when_the_switch_failed_and_two_layouts_are_installed(uint current, uint target, int installed, bool expected) =>
        Assert.Equal(expected, LayoutSwitcher.NeedsWinSpace(current, target, installed));
}
