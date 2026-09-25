namespace GibberishRewriter.App.Tests;

/// <summary>A fresh folder under %TEMP%, deleted afterwards.</summary>
internal sealed class TempFolder : IDisposable
{
    public TempFolder() => Directory.CreateDirectory(Root);

    public string Root { get; } = Path.Combine(Path.GetTempPath(), "GibberishRewriterTests", Guid.NewGuid().ToString("N"));

    public string PathOf(string relative) => Path.Combine(Root, relative.Replace('/', Path.DirectorySeparatorChar));

    public void Dispose() => Directory.Delete(Root, recursive: true);
}
