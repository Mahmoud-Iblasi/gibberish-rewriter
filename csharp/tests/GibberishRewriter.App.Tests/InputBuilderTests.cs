using System.Runtime.InteropServices;
using GibberishRewriter.App.Win;
using static GibberishRewriter.App.Win.NativeMethods;
using Shortcut = GibberishRewriter.Core.Shortcut;

namespace GibberishRewriter.App.Tests;

public class InputBuilderTests
{
    [Fact]
    public void INPUT_has_the_size_SendInput_expects() =>
        Assert.Equal(IntPtr.Size == 8 ? 40 : 28, Marshal.SizeOf<INPUT>());

    [Fact]
    public void Every_event_carries_the_app_marker() =>
        Assert.All(
            [.. InputBuilder.Backspaces(1), .. InputBuilder.Text("a"), .. InputBuilder.WinSpace(), .. InputBuilder.KeyPress(0xE8)],
            input =>
            {
                Assert.Equal(INPUT_KEYBOARD, input.type);
                Assert.Equal((UIntPtr)0x47525752u, input.u.ki.dwExtraInfo);
            });

    [Fact]
    public void Backspaces_press_and_release_VK_BACK() =>
        Assert.Equal("08v 08^ 08v 08^", Describe(InputBuilder.Backspaces(2)));

    [Fact]
    public void Text_sends_each_UTF16_unit_as_a_unicode_down_and_up()
    {
        var events = InputBuilder.Text("لا😀");
        Assert.Equal(new ushort[] { 0x0644, 0x0644, 0x0627, 0x0627, 0xD83D, 0xD83D, 0xDE00, 0xDE00 }, events.Select(e => e.u.ki.wScan));
        Assert.All(events, e => Assert.Equal(0, e.u.ki.wVk));
        Assert.Equal(
            new uint[] { 4, 6, 4, 6, 4, 6, 4, 6 },
            events.Select(e => e.u.ki.dwFlags));
    }

    [Theory]
    [InlineData(Shortcut.Copy, false, "11v 43v 43^ 11^")]
    [InlineData(Shortcut.Paste, false, "11v 56v 56^ 11^")]
    [InlineData(Shortcut.Undo, false, "11v 5Av 5A^ 11^")]
    [InlineData(Shortcut.Copy, true, "11v 2Dve 2D^e 11^")]
    [InlineData(Shortcut.Paste, true, "10v 2Dve 2D^e 10^")]
    [InlineData(Shortcut.Undo, true, "11v 5Av 5A^ 11^")]
    public void Shortcut_uses_Insert_variants_in_consoles(Shortcut shortcut, bool console, string expected) =>
        Assert.Equal(expected, Describe(InputBuilder.Shortcut(shortcut, console)));

    [Fact]
    public void WinSpace_presses_left_Win_then_Space() =>
        Assert.Equal("5Bve 20v 20^ 5B^e", Describe(InputBuilder.WinSpace()));

    [Fact]
    public void KeyPress_is_one_down_and_up() =>
        Assert.Equal("E8v E8^", Describe(InputBuilder.KeyPress(0xE8)));

    [Fact]
    public void Chunks_hold_at_most_50_events() =>
        Assert.Equal(new[] { 50, 50, 20 }, InputBuilder.Chunks(InputBuilder.Text(new string('a', 60))).Select(chunk => chunk.Length));

    /// <summary>"vk" in hex, then v for down or ^ for up, then e when KEYEVENTF_EXTENDEDKEY is set.</summary>
    private static string Describe(INPUT[] events) =>
        string.Join(" ", events.Select(e =>
            $"{e.u.ki.wVk:X2}{((e.u.ki.dwFlags & KEYEVENTF_KEYUP) != 0 ? "^" : "v")}{((e.u.ki.dwFlags & KEYEVENTF_EXTENDEDKEY) != 0 ? "e" : "")}"));

    /// <summary>A surrogate pair is four events and ChunkSize is 50, so a boundary can fall inside one. Windows
    /// wants the pair in a single SendInput call.</summary>
    [Theory]
    [InlineData(0)]
    [InlineData(1)]
    [InlineData(2)]
    [InlineData(23)]
    [InlineData(24)]
    [InlineData(25)]
    [InlineData(26)]
    public void Chunks_never_split_a_surrogate_pair(int lead)
    {
        var text = new string('a', lead) + "😀" + new string('b', 40);
        var chunks = InputBuilder.Chunks(InputBuilder.Text(text)).ToList();

        Assert.Equal(text.Length * 2, chunks.Sum(chunk => chunk.Length));
        Assert.All(chunks, chunk => Assert.True(chunk.Length is > 0 and <= InputBuilder.ChunkSize));
        foreach (var chunk in chunks)
        {
            var scans = chunk
                .Where(input => (input.u.ki.dwFlags & NativeMethods.KEYEVENTF_UNICODE) != 0)
                .Select(input => (char)input.u.ki.wScan)
                .ToList();
            Assert.Equal(scans.Count(char.IsHighSurrogate), scans.Count(char.IsLowSurrogate));
        }
    }
}
