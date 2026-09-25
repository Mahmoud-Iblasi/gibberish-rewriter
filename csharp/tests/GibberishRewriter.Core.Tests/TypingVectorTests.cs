using GibberishRewriter.Core.Tests.Harness;

namespace GibberishRewriter.Core.Tests;

public class TypingVectorTests
{
    private const string File = "vectors/typing.json";

    public static IEnumerable<object[]> VectorNames() => VectorFile.Names(File);

    [Theory]
    [MemberData(nameof(VectorNames))]
    public void Typing_vector(string name)
    {
        var vector = VectorFile.Get(File, name);
        var runner = new VectorRunner(vector);
        runner.Run(vector.GetProperty("events"));
        Assert.Equal(VectorRunner.ExpectedCalls(vector), runner.Platform.Calls);
    }
}
