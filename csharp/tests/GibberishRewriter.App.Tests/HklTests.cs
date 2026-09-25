using GibberishRewriter.App.Win;
using GibberishRewriter.Core;

namespace GibberishRewriter.App.Tests;

public class HklTests
{
    [Fact]
    public void Low32_drops_the_sign_extension_of_64_bit_handles() =>
        Assert.Equal(0xF0C00409u, Hkl.Low32(new IntPtr(unchecked((long)0xFFFFFFFFF0C00409))));

    [Fact]
    public void ToHandle_sign_extends_like_GetKeyboardLayoutList()
    {
        Assert.Equal(unchecked((long)0xFFFFFFFFF0C00409), Hkl.ToHandle(0xF0C00409).ToInt64());
        Assert.Equal(0x04090409L, Hkl.ToHandle(0x04090409).ToInt64());
    }

    [Theory]
    [InlineData(0x04090409u, "04090409")]
    [InlineData(0x04012C01u, "04012C01")]
    [InlineData(0xF0C00409u, "F0C00409")]
    public void Format_and_Parse_round_trip(uint hkl, string text)
    {
        Assert.Equal(text, Hkl.Format(hkl));
        Assert.Equal(hkl, Hkl.Parse(text));
        Assert.Equal(hkl, Hkl.Parse(text.ToLowerInvariant()));
    }

    [Fact]
    public void LayoutPair_maps_handles_to_kinds()
    {
        var pair = new LayoutPair(0x04090409, 0x04012C01);
        Assert.Equal(LayoutKind.Latin, pair.KindOf(new IntPtr(0x04090409)));
        Assert.Equal(LayoutKind.Arabic, pair.KindOf(0x04012C01u));
        Assert.Null(pair.KindOf(0x04070407u));
        Assert.Equal(0x04012C01u, pair.HklOf(LayoutKind.Arabic));
    }
}
