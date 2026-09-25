using GibberishRewriter.App.Win;
using GibberishRewriter.Core;

namespace GibberishRewriter.App.Tests;

public class HookTranslatorTests
{
    [Theory]
    [InlineData(0x0100, true)]
    [InlineData(0x0104, true)]
    [InlineData(0x0101, false)]
    [InlineData(0x0105, false)]
    public void IsKeyDown_is_true_for_WM_KEYDOWN_and_WM_SYSKEYDOWN(int message, bool expected) =>
        Assert.Equal(expected, HookTranslator.IsKeyDown(message));

    [Theory]
    [InlineData(0x10u, 0x47525752u, true)]
    [InlineData(0x10u, 0x12345678u, false)]
    [InlineData(0x00u, 0x47525752u, false)]
    public void IsInjectedBySelf_needs_the_injected_flag_and_the_app_marker(uint flags, uint extraInfo, bool expected) =>
        Assert.Equal(expected, HookTranslator.IsInjectedBySelf(flags, (UIntPtr)extraInfo));

    [Fact]
    public void Modifiers_reads_Shift_Ctrl_Alt_and_either_Win_key()
    {
        Assert.Equal(HoldKeys.None, HookTranslator.Modifiers(_ => false));
        Assert.Equal(HoldKeys.Shift | HoldKeys.Alt, HookTranslator.Modifiers(vk => vk is 0x10 or 0x12));
        Assert.Equal(HoldKeys.Ctrl | HoldKeys.Win, HookTranslator.Modifiers(vk => vk is 0x11 or 0x5C));
        Assert.Equal(HoldKeys.Win, HookTranslator.Modifiers(vk => vk == 0x5B));
    }

    [Theory]
    [InlineData(0x0201, true)]
    [InlineData(0x0204, true)]
    [InlineData(0x0207, true)]
    [InlineData(0x020B, true)]
    [InlineData(0x0200, false)]
    [InlineData(0x0202, false)]
    [InlineData(0x020A, false)]
    public void IsMouseButtonDown_is_true_only_for_button_presses(int message, bool expected) =>
        Assert.Equal(expected, HookTranslator.IsMouseButtonDown(message));
}

public class KeyStateTrackerTests
{
    [Fact]
    public void Tracks_downs_and_ups_and_clears()
    {
        var keys = new KeyStateTracker();
        keys.Set(0x14, true);
        keys.Set(0x09, true);
        keys.Set(0x09, false);
        Assert.True(keys.IsDown(0x14));
        Assert.False(keys.IsDown(0x09));

        keys.Clear();

        Assert.False(keys.IsDown(0x14));
    }

    [Fact]
    public void Ignores_codes_outside_0_to_255()
    {
        var keys = new KeyStateTracker();
        keys.Set(300, true);
        keys.Set(-1, true);
        Assert.False(keys.IsDown(300));
        Assert.False(keys.IsDown(-1));
    }
}

public class HookWatchdogTests
{
    [Theory]
    [InlineData(12_001u, 10_000u, false, true)]
    [InlineData(12_000u, 10_000u, false, false)]
    [InlineData(12_001u, 10_000u, true, false)]
    [InlineData(10_000u, 12_001u, false, false)]
    [InlineData(0x0000_0800u, 0xFFFF_FF00u, false, true)]
    public void IsStale_needs_input_more_than_2_s_after_the_last_hook_event(uint lastInput, uint lastHook, bool blocked, bool expected) =>
        Assert.Equal(expected, HookWatchdog.IsStale(lastInput, lastHook, blocked));

    [Fact]
    public void The_missed_input_message_names_the_gap_and_the_foreground_class() =>
        Assert.Equal(
            "The hooks missed input for 2001 ms (foreground: Chrome_WidgetWin_1); reinstalling them",
            HookWatchdog.MissedInputMessage(2001, "Chrome_WidgetWin_1"));

    [Fact]
    public void HookActivity_keeps_times_above_int_MaxValue()
    {
        var activity = new HookActivity();
        activity.Note(0xFFFF_FF00);
        Assert.Equal(0xFFFF_FF00u, activity.LastEventTime);
    }
}
