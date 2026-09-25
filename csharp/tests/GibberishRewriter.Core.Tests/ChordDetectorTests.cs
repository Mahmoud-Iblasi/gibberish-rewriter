namespace GibberishRewriter.Core.Tests;

public class ChordDetectorTests
{
    private const int Tab = 0x09;
    private const int Backquote = 0xC0;
    private const int CapsLock = 0x14;
    private const int ShiftLeft = 0xA0;
    private const int KeyA = 0x41;
    private const int F9 = 0x78;
    private const int F10 = 0x79;

    private static readonly KeyNames Names = KeyNames.Load(SharedFiles.PathOf("keys.json"));

    private static ChordDetector Detector() => new(
        Names,
        new Chord(HoldKeys.Shift | HoldKeys.CapsLock, Tab),
        new Chord(HoldKeys.Shift | HoldKeys.CapsLock, Backquote));

    [Fact]
    public void Chord_fires_on_trigger_down_and_swallows_the_trigger_repeats_and_up()
    {
        var detector = Detector();
        Assert.Equal(ChordDecision.Pass, detector.OnKey(ShiftLeft, true, HoldKeys.None));
        Assert.Equal(ChordDecision.SwallowKey, detector.OnKey(CapsLock, true, HoldKeys.Shift));
        Assert.Equal(new ChordDecision(true, ChordAction.FixTyped), detector.OnKey(Tab, true, HoldKeys.Shift));
        Assert.Equal(ChordDecision.SwallowKey, detector.OnKey(Tab, true, HoldKeys.Shift));
        Assert.Equal(ChordDecision.SwallowKey, detector.OnKey(Tab, false, HoldKeys.Shift));
        Assert.Equal(ChordDecision.SwallowKey, detector.OnKey(CapsLock, false, HoldKeys.Shift));
        Assert.Equal(ChordDecision.Pass, detector.OnKey(ShiftLeft, false, HoldKeys.Shift));
    }

    [Fact]
    public void Hold_keys_can_be_pressed_in_any_order()
    {
        var detector = Detector();
        Assert.Equal(ChordDecision.SwallowKey, detector.OnKey(CapsLock, true, HoldKeys.None));
        Assert.Equal(ChordDecision.Pass, detector.OnKey(ShiftLeft, true, HoldKeys.None));
        Assert.Equal(ChordAction.FixSelection, detector.OnKey(Backquote, true, HoldKeys.Shift).Fired);
    }

    [Fact]
    public void A_CapsLock_tap_is_swallowed_and_replayed_on_release()
    {
        var detector = Detector();
        Assert.Equal(ChordDecision.SwallowKey, detector.OnKey(CapsLock, true, HoldKeys.None));
        Assert.Equal(ChordDecision.SwallowKey, detector.OnKey(CapsLock, true, HoldKeys.None));
        Assert.Equal(
            new ChordDecision(true, ReplayCapsLock: true, CapsLockToggled: true),
            detector.OnKey(CapsLock, false, HoldKeys.None));
        Assert.False(detector.CapsLockDown);
    }

    [Fact]
    public void CapsLock_held_while_typing_is_still_replayed()
    {
        var detector = Detector();
        detector.OnKey(CapsLock, true, HoldKeys.None);
        Assert.True(detector.CapsLockDown);
        Assert.Equal(ChordDecision.Pass, detector.OnKey(KeyA, true, HoldKeys.None));
        Assert.Equal(ChordDecision.Pass, detector.OnKey(KeyA, false, HoldKeys.None));
        Assert.True(detector.OnKey(CapsLock, false, HoldKeys.None).ReplayCapsLock);
    }

    [Fact]
    public void A_CapsLock_up_without_a_down_is_swallowed_without_a_replay() =>
        Assert.Equal(ChordDecision.SwallowKey, Detector().OnKey(CapsLock, false, HoldKeys.None));

    [Fact]
    public void An_extra_held_modifier_stops_the_chord()
    {
        var detector = Detector();
        detector.OnKey(CapsLock, true, HoldKeys.None);
        Assert.Equal(ChordDecision.Pass, detector.OnKey(Tab, true, HoldKeys.Shift | HoldKeys.Ctrl));
    }

    [Fact]
    public void A_missing_hold_key_stops_the_chord()
    {
        var detector = Detector();
        Assert.Equal(ChordDecision.Pass, detector.OnKey(Tab, true, HoldKeys.Shift));
        Assert.Equal(ChordDecision.Pass, detector.OnKey(Tab, false, HoldKeys.Shift));
        detector.OnKey(CapsLock, true, HoldKeys.None);
        Assert.Equal(ChordDecision.Pass, detector.OnKey(Tab, true, HoldKeys.None));
    }

    [Fact]
    public void Both_triggers_held_at_once_each_keep_their_key_up_swallowed()
    {
        var detector = Detector();
        detector.OnKey(ShiftLeft, true, HoldKeys.None);
        detector.OnKey(CapsLock, true, HoldKeys.Shift);
        Assert.Equal(ChordAction.FixTyped, detector.OnKey(Tab, true, HoldKeys.Shift).Fired);
        Assert.Equal(ChordAction.FixSelection, detector.OnKey(Backquote, true, HoldKeys.Shift).Fired);
        Assert.Equal(ChordDecision.SwallowKey, detector.OnKey(Tab, false, HoldKeys.Shift));
        Assert.Equal(ChordDecision.SwallowKey, detector.OnKey(Backquote, false, HoldKeys.Shift));
    }

    [Fact]
    public void Modifier_keys_always_pass()
    {
        var detector = Detector();
        foreach (var vk in new[] { 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C, 0x90, 0x91, 0x10 })
        {
            Assert.Equal(ChordDecision.Pass, detector.OnKey(vk, true, HoldKeys.None));
            Assert.Equal(ChordDecision.Pass, detector.OnKey(vk, false, HoldKeys.None));
        }
    }

    [Fact]
    public void CapsLock_passes_and_reports_toggles_when_no_chord_holds_it()
    {
        var detector = new ChordDetector(Names, new Chord(HoldKeys.Ctrl | HoldKeys.Alt, F9), new Chord(HoldKeys.Ctrl | HoldKeys.Alt, F10));
        Assert.Equal(new ChordDecision(false, CapsLockToggled: true), detector.OnKey(CapsLock, true, HoldKeys.None));
        Assert.Equal(ChordDecision.Pass, detector.OnKey(CapsLock, true, HoldKeys.None));
        Assert.Equal(ChordDecision.Pass, detector.OnKey(CapsLock, false, HoldKeys.None));
    }

    [Fact]
    public void A_held_CapsLock_counts_as_an_extra_key_for_chords_without_it()
    {
        var detector = new ChordDetector(Names, new Chord(HoldKeys.Ctrl, F9), new Chord(HoldKeys.Ctrl, F10));
        detector.OnKey(CapsLock, true, HoldKeys.None);
        Assert.Equal(ChordDecision.Pass, detector.OnKey(F9, true, HoldKeys.Ctrl));
    }

    [Theory]
    [InlineData(HoldKeys.Ctrl | HoldKeys.Alt, true)]
    [InlineData(HoldKeys.Win, true)]
    [InlineData(HoldKeys.Ctrl | HoldKeys.Shift, false)]
    public void Chords_holding_Alt_or_Win_ask_for_the_mask_key(HoldKeys hold, bool expected)
    {
        var detector = new ChordDetector(Names, new Chord(hold, F9), new Chord(hold, F10));
        var decision = detector.OnKey(F9, true, hold);
        Assert.Equal(ChordAction.FixTyped, decision.Fired);
        Assert.Equal(expected, decision.SendMaskKey);
    }

    [Fact]
    public void SetChords_forgets_a_half_pressed_chord()
    {
        var detector = Detector();
        detector.OnKey(CapsLock, true, HoldKeys.None);
        detector.SetChords(new Chord(HoldKeys.Shift | HoldKeys.CapsLock, Tab), new Chord(HoldKeys.Shift | HoldKeys.CapsLock, Backquote));
        Assert.False(detector.CapsLockDown);
        Assert.Equal(ChordDecision.SwallowKey, detector.OnKey(CapsLock, false, HoldKeys.None));
    }
}
