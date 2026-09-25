using GibberishRewriter.Core.Tests.Harness;

namespace GibberishRewriter.Core.Tests;

public class ChordVectorTests
{
    private const string File = "vectors/chords.json";

    public static IEnumerable<object[]> VectorNames() => VectorFile.Names(File);

    [Theory]
    [MemberData(nameof(VectorNames))]
    public void Chord_vector(string name)
    {
        var vector = VectorFile.Get(File, name);
        var runner = new VectorRunner(vector);
        runner.Run(vector.GetProperty("events"));
        Assert.Equal(
            vector.GetProperty("expect").EnumerateArray().Select(decision => decision.GetString()!).ToList(),
            runner.Decisions);
    }

    [Fact]
    public void Keys_the_app_injected_always_pass_untouched()
    {
        var runner = new VectorRunner(VectorFile.Get(File, "CapsLock tap toggles on release"));
        var decision = runner.Engine.OnKey(new KeyEvent(KeyNames.VkCapsLock, true, true, false, HoldKeys.None, 1, LayoutKind.Latin));
        Assert.False(decision.Swallow);
        Assert.Empty(decision.SendKeys);
    }
}
