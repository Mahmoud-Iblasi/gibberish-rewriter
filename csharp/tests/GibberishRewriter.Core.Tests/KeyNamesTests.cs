namespace GibberishRewriter.Core.Tests;

public class KeyNamesTests
{
    private static readonly KeyNames Names = KeyNames.Load(SharedFiles.PathOf("keys.json"));

    [Theory]
    [InlineData("Tab", 0x09)]
    [InlineData("tab", 0x09)]
    [InlineData("KEYQ", 0x51)]
    [InlineData("Backquote", 0xC0)]
    [InlineData("`", 0xC0)]
    [InlineData("F24", 0x87)]
    [InlineData("NumpadDivide", 0x6F)]
    public void Trigger_names_are_case_insensitive_and_accept_a_backtick(string name, int expected)
    {
        Assert.True(Names.TryGetTrigger(name, out var vk));
        Assert.Equal(expected, vk);
    }

    [Theory]
    [InlineData("ShiftLeft")]
    [InlineData("Shift")]
    [InlineData("CapsLock")]
    [InlineData("NumLock")]
    public void Modifier_names_are_not_triggers(string name)
    {
        Assert.False(Names.TryGetTrigger(name, out _));
        Assert.True(Names.IsModifierName(name));
    }

    [Theory]
    [InlineData("ShiftLeft", 0xA0)]
    [InlineData("MetaRight", 0x5C)]
    [InlineData("KeyA", 0x41)]
    public void TryGetVk_finds_modifiers_and_other_keys(string name, int expected)
    {
        Assert.True(Names.TryGetVk(name, out var vk));
        Assert.Equal(expected, vk);
    }

    [Theory]
    [InlineData("shift", HoldKeys.Shift)]
    [InlineData("Ctrl", HoldKeys.Ctrl)]
    [InlineData("WIN", HoldKeys.Win)]
    [InlineData("capslock", HoldKeys.CapsLock)]
    public void Hold_key_names_are_case_insensitive(string name, HoldKeys expected)
    {
        Assert.True(Names.TryGetHoldKey(name, out var hold));
        Assert.Equal(expected, hold);
    }

    [Theory]
    [InlineData(0xA0, HoldKeys.Shift)]
    [InlineData(0xA1, HoldKeys.Shift)]
    [InlineData(0x10, HoldKeys.Shift)]
    [InlineData(0xA3, HoldKeys.Ctrl)]
    [InlineData(0xA5, HoldKeys.Alt)]
    [InlineData(0x5C, HoldKeys.Win)]
    [InlineData(0x14, HoldKeys.CapsLock)]
    [InlineData(0x41, HoldKeys.None)]
    public void HoldKeyOf_maps_left_right_and_sideless_codes(int vk, HoldKeys expected) =>
        Assert.Equal(expected, Names.HoldKeyOf(vk));

    [Theory]
    [InlineData(0x90, true)]
    [InlineData(0x91, true)]
    [InlineData(0x14, true)]
    [InlineData(0xA2, true)]
    [InlineData(0x11, true)]
    [InlineData(0x41, false)]
    [InlineData(0x09, false)]
    public void IsModifier_covers_hold_keys_and_lock_keys(int vk, bool expected) =>
        Assert.Equal(expected, Names.IsModifier(vk));

    [Fact]
    public void VksOf_lists_codes_in_canonical_order() =>
        Assert.Equal(new[] { 0xA0, 0xA1, 0x10, 0x14 }, Names.VksOf(HoldKeys.CapsLock | HoldKeys.Shift));

    [Theory]
    [InlineData(0xC0, "Backquote")]
    [InlineData(0xA0, "ShiftLeft")]
    [InlineData(0xE8, "0xE8")]
    public void NameOf_returns_the_name_from_keys_json(int vk, string expected) =>
        Assert.Equal(expected, Names.NameOf(vk));

    [Fact]
    public void TableKeys_are_the_snapshot_keys_in_order() =>
        Assert.Equal(
            KeyTable.Load(SharedFiles.PathOf("layouts/us-arabic101.json")).Keys.Select(entry => entry.Key),
            Names.TableKeys);

    [Fact]
    public void Every_table_key_has_its_snapshot_code()
    {
        foreach (var entry in KeyTable.Load(SharedFiles.PathOf("layouts/us-arabic101.json")).Keys)
        {
            Assert.True(Names.TryGetTrigger(entry.Key, out var vk));
            Assert.Equal(entry.Vk, vk);
        }
    }

    [Fact]
    public void Parse_rejects_a_table_key_missing_from_keys() =>
        Assert.Throws<FormatException>(() => KeyNames.Parse(
            """{ "keys": { "KeyA": 65 }, "modifiers": {}, "holdKeys": {}, "tableKeys": [ "KeyB" ] }"""));
}
