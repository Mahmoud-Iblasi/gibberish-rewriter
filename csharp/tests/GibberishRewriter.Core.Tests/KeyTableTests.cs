namespace GibberishRewriter.Core.Tests;

public class KeyTableTests
{
    private static readonly KeyTable Table = KeyTable.Load(SharedFiles.PathOf("layouts/us-arabic101.json"));

    [Fact]
    public void Snapshot_has_the_64_keys_of_spec_4_1_with_codes_from_keys_json()
    {
        var names = KeyNames.Load(SharedFiles.PathOf("keys.json"));
        Assert.Equal(64, Table.Keys.Count);
        Assert.Equal("Backquote", Table.Keys[0].Key);
        Assert.Equal("NumpadDivide", Table.Keys[^1].Key);
        foreach (var entry in Table.Keys)
        {
            Assert.True(names.TryGetTrigger(entry.Key, out var vk), entry.Key);
            Assert.Equal(vk, entry.Vk);
        }
    }

    [Fact]
    public void Snapshot_records_the_layout_handles()
    {
        Assert.Equal("04090409", Table.LatinHkl);
        Assert.Equal("04012C01", Table.ArabicHkl);
    }

    [Theory]
    [InlineData(0x48, LayoutKind.Arabic, KeyState.Plain, "\u0627")]
    [InlineData(0x48, LayoutKind.Latin, KeyState.Caps, "H")]
    [InlineData(0x48, LayoutKind.Latin, KeyState.ShiftCaps, "h")]
    [InlineData(0x48, LayoutKind.Arabic, KeyState.Caps, "\u0627")]
    [InlineData(0x42, LayoutKind.Arabic, KeyState.Plain, "\u0644\u0627")]
    [InlineData(0x42, LayoutKind.Arabic, KeyState.Shift, "\u0644\u0622")]
    [InlineData(0xC0, LayoutKind.Arabic, KeyState.Shift, "\u0651")]
    [InlineData(0xBF, LayoutKind.Arabic, KeyState.Shift, "\u061F")]
    [InlineData(0x6F, LayoutKind.Latin, KeyState.Plain, "/")]
    [InlineData(0x60, LayoutKind.Arabic, KeyState.Shift, "")]
    [InlineData(0x09, LayoutKind.Latin, KeyState.Plain, "")]
    public void TextOf_reads_the_snapshot(int vk, LayoutKind layout, KeyState state, string expected) =>
        Assert.Equal(expected, Table.TextOf(vk, layout, state));

    [Theory]
    [InlineData("/", LayoutKind.Latin, "Slash", KeyState.Plain)]
    [InlineData("?", LayoutKind.Latin, "Slash", KeyState.Shift)]
    [InlineData("1", LayoutKind.Latin, "Digit1", KeyState.Plain)]
    [InlineData("+", LayoutKind.Latin, "Equal", KeyState.Shift)]
    [InlineData("\\", LayoutKind.Latin, "Backslash", KeyState.Plain)]
    [InlineData("\u0644", LayoutKind.Arabic, "KeyG", KeyState.Plain)]
    [InlineData("\u0644\u0627", LayoutKind.Arabic, "KeyB", KeyState.Plain)]
    [InlineData("\u0623", LayoutKind.Arabic, "KeyH", KeyState.Shift)]
    public void Find_takes_the_first_key_in_table_order_trying_plain_before_shift(
        string text, LayoutKind layout, string expectedKey, KeyState expectedState)
    {
        var found = Table.Find(text, layout);
        Assert.NotNull(found);
        Assert.Equal(expectedKey, found.Value.Entry.Key);
        Assert.Equal(expectedState, found.Value.State);
    }

    [Theory]
    [InlineData("")]
    [InlineData("ab")]
    [InlineData("\n")]
    public void Find_returns_null_for_text_no_key_types(string text) =>
        Assert.Null(Table.Find(text, LayoutKind.Latin));

    [Theory]
    [InlineData(false, false, KeyState.Plain)]
    [InlineData(true, false, KeyState.Shift)]
    [InlineData(false, true, KeyState.Caps)]
    [InlineData(true, true, KeyState.ShiftCaps)]
    public void StateOf_combines_shift_and_caps_lock(bool shift, bool capsOn, KeyState expected) =>
        Assert.Equal(expected, LayoutKinds.StateOf(shift, capsOn));

    [Fact]
    public void Layout_kind_helpers_round_trip()
    {
        Assert.Equal(LayoutKind.Arabic, LayoutKind.Latin.Other());
        Assert.Equal(LayoutKind.Latin, LayoutKind.Arabic.Other());
        Assert.Equal("arabic", LayoutKind.Arabic.ToName());
        Assert.Equal(LayoutKind.Latin, LayoutKinds.Parse("latin"));
        Assert.Throws<ArgumentException>(() => LayoutKinds.Parse("other"));
    }

    [Fact]
    public void ToJson_round_trips_through_Parse()
    {
        var copy = KeyTable.Parse(Table.ToJson());
        Assert.Equal(Table.LatinHkl, copy.LatinHkl);
        Assert.Equal(Table.ArabicHkl, copy.ArabicHkl);
        Assert.Equal(Table.Keys.Count, copy.Keys.Count);
        for (var i = 0; i < Table.Keys.Count; i++)
        {
            Assert.Equal(Table.Keys[i].Key, copy.Keys[i].Key);
            Assert.Equal(Table.Keys[i].Vk, copy.Keys[i].Vk);
            Assert.Equal(Table.Keys[i].Latin, copy.Keys[i].Latin);
            Assert.Equal(Table.Keys[i].Arabic, copy.Keys[i].Arabic);
        }
    }
}
