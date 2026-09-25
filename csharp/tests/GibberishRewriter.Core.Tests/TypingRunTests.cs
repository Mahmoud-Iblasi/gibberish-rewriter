namespace GibberishRewriter.Core.Tests;

public class TypingRunTests
{
    private static readonly KeyTable Table = KeyTable.Load(SharedFiles.PathOf("layouts/us-arabic101.json"));

    /// <summary>A plain key press on the Arabic layout. <paramref name="key"/> is the letter on the key cap.</summary>
    private static KeyRecord OnArabic(char key) => new(
        key, false, false,
        Table.TextOf(key, LayoutKind.Arabic, KeyState.Plain),
        Table.TextOf(key, LayoutKind.Latin, KeyState.Plain));

    private static TypingRun ArabicRun(string keys, int maxLength = 1000)
    {
        var run = new TypingRun(maxLength);
        foreach (var key in keys)
        {
            run.Record(1, LayoutKind.Arabic, OnArabic(key));
        }
        return run;
    }

    [Fact]
    public void Records_join_into_the_run_text_and_the_other_layout_text()
    {
        var run = ArabicRun("HELLO");
        Assert.Equal("اثممخ", run.Text);
        Assert.Equal("hello", run.OtherText);
        Assert.Equal(LayoutKind.Arabic, run.Layout);
        Assert.Equal(1L, run.Window);
        Assert.False(run.Sealed);
    }

    [Fact]
    public void A_different_window_starts_a_new_run()
    {
        var run = ArabicRun("HE");
        run.Record(2, LayoutKind.Arabic, OnArabic('L'));
        Assert.Equal("l", run.OtherText);
        Assert.Equal(2L, run.Window);
    }

    [Fact]
    public void A_different_layout_starts_a_new_run()
    {
        var run = ArabicRun("HE");
        run.Record(1, LayoutKind.Latin, new KeyRecord('L', false, false, "l", "م"));
        Assert.Equal("l", run.Text);
        Assert.Equal(LayoutKind.Latin, run.Layout);
    }

    [Fact]
    public void The_oldest_records_are_dropped_past_the_maximum() =>
        Assert.Equal("llo", ArabicRun("HELLO", maxLength: 3).OtherText);

    [Fact]
    public void Lowering_the_maximum_drops_the_oldest_records()
    {
        var run = ArabicRun("HELLO");
        run.MaxLength = 2;
        Assert.Equal("lo", run.OtherText);
    }

    [Fact]
    public void Backspace_removes_the_last_record()
    {
        var run = ArabicRun("HEL");
        run.Backspace(Table);
        Assert.Equal("he", run.OtherText);
    }

    [Fact]
    public void Backspace_on_an_empty_run_does_nothing()
    {
        var run = new TypingRun(10);
        run.Backspace(Table);
        Assert.True(run.IsEmpty);
    }

    [Fact]
    public void Backspace_on_lam_alef_leaves_lam()
    {
        var run = ArabicRun("AB");
        Assert.Equal("شلا", run.Text);
        run.Backspace(Table);
        Assert.Equal("شل", run.Text);
        Assert.Equal("ag", run.OtherText);
        Assert.Equal((int)'G', run.Records[^1].Vk);
    }

    [Fact]
    public void Backspace_on_shifted_lam_alef_leaves_lam()
    {
        var run = new TypingRun(10);
        run.Record(1, LayoutKind.Arabic, new KeyRecord('B', true, false, "لآ", "B"));
        run.Backspace(Table);
        Assert.Equal("ل", run.Text);
        Assert.Equal("g", run.OtherText);
    }

    [Fact]
    public void SwapAfterFix_swaps_texts_moves_to_the_other_layout_and_seals()
    {
        var run = ArabicRun("HELLO");
        run.SwapAfterFix();
        Assert.Equal("hello", run.Text);
        Assert.Equal("اثممخ", run.OtherText);
        Assert.Equal(LayoutKind.Latin, run.Layout);
        Assert.True(run.Sealed);

        run.SwapAfterFix();
        Assert.Equal("اثممخ", run.Text);
        Assert.Equal(LayoutKind.Arabic, run.Layout);
        Assert.True(run.Sealed);
    }

    [Fact]
    public void SwapAfterFix_on_an_empty_run_does_nothing()
    {
        var run = new TypingRun(10);
        run.SwapAfterFix();
        Assert.False(run.Sealed);
        Assert.Equal(LayoutKind.Latin, run.Layout);
    }

    [Fact]
    public void The_next_record_clears_a_sealed_run()
    {
        var run = ArabicRun("HI");
        run.SwapAfterFix();
        run.Record(1, LayoutKind.Latin, new KeyRecord('A', false, false, "a", "ش"));
        Assert.Equal("a", run.Text);
        Assert.False(run.Sealed);
    }

    [Fact]
    public void Backspace_clears_a_sealed_run()
    {
        var run = ArabicRun("HI");
        run.SwapAfterFix();
        run.Backspace(Table);
        Assert.True(run.IsEmpty);
        Assert.False(run.Sealed);
    }

    [Fact]
    public void Clear_empties_and_unseals()
    {
        var run = ArabicRun("HI");
        run.SwapAfterFix();
        run.Clear();
        Assert.True(run.IsEmpty);
        Assert.False(run.Sealed);
        Assert.Equal("", run.Text);
    }
}
