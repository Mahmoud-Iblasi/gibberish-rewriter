namespace GibberishRewriter.App.Tests;

/// <summary>A test that touches real Windows state (clipboard, mutexes, installed layouts). It runs only when
/// GIBBERISH_INTEGRATION=1, so a normal test run never changes the user's clipboard.</summary>
public sealed class IntegrationFactAttribute : FactAttribute
{
    public const string Variable = "GIBBERISH_INTEGRATION";

    public IntegrationFactAttribute()
    {
        if (!Enabled)
        {
            Skip = $"Windows integration test. Set {Variable}=1 to run it.";
        }
    }

    public static bool Enabled => Environment.GetEnvironmentVariable(Variable) == "1";
}
