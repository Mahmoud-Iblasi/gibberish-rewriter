namespace GibberishRewriter.App.Win;

/// <summary>The named mutex both apps take.</summary>
internal static class SingleInstance
{
    public const string MutexName = @"Local\GibberishRewriter.SingleInstance";

    /// <summary>The mutex, held; or null when another copy (C# or Python) holds it. Keep it until the app exits.</summary>
    public static Mutex? TryAcquire(string name = MutexName)
    {
        var mutex = new Mutex(initiallyOwned: true, name, out var createdNew);
        if (createdNew)
        {
            return mutex;
        }
        mutex.Dispose();
        return null;
    }
}
