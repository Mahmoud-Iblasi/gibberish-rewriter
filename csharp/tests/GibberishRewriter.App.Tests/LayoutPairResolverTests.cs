using GibberishRewriter.App.Win;

namespace GibberishRewriter.App.Tests;

public class LayoutPairResolverTests
{
    private const uint English = 0x04090409;
    private const uint Arabic = 0x04012C01;
    private const uint German = 0x04070407;
    private const uint Russian = 0x04190419;

    private static readonly (uint Hkl, string KeyA)[] UserLayouts = [(English, "a"), (Arabic, "ش")];

    [Fact]
    public void Auto_picks_the_one_Latin_and_the_one_Arabic_layout()
    {
        var result = LayoutPairResolver.Resolve("auto", "auto", UserLayouts);
        Assert.Equal(new LayoutPair(English, Arabic), result.Pair);
        Assert.Null(result.Error);
    }

    [Fact]
    public void Auto_ignores_layouts_of_other_scripts() =>
        Assert.Equal(
            new LayoutPair(English, Arabic),
            LayoutPairResolver.Resolve("auto", "auto", [(Russian, "ф"), .. UserLayouts]).Pair);

    [Fact]
    public void Auto_with_two_Latin_layouts_asks_for_explicit_values()
    {
        var result = LayoutPairResolver.Resolve("auto", "auto", [(German, "a"), .. UserLayouts]);
        Assert.Null(result.Pair);
        Assert.Equal(AppMessages.LayoutsNotFound, result.Error);
    }

    [Fact]
    public void Auto_without_an_Arabic_layout_asks_for_explicit_values() =>
        Assert.Equal(AppMessages.LayoutsNotFound, LayoutPairResolver.Resolve("auto", "auto", [(English, "a")]).Error);

    [Fact]
    public void An_explicit_value_chooses_among_several_Latin_layouts() =>
        Assert.Equal(
            new LayoutPair(German, Arabic),
            LayoutPairResolver.Resolve("04070407", "auto", [(German, "a"), .. UserLayouts]).Pair);

    [Fact]
    public void An_explicit_layout_that_is_not_installed_keeps_the_app_disabled() =>
        Assert.Equal(
            AppMessages.LayoutNotInstalled("040C040C"),
            LayoutPairResolver.Resolve("040C040C", "auto", UserLayouts).Error);

    [Fact]
    public void The_same_layout_twice_is_rejected() =>
        Assert.Equal(AppMessages.LayoutsSame, LayoutPairResolver.Resolve("04090409", "04090409", UserLayouts).Error);
}
