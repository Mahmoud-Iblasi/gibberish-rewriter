namespace GibberishRewriter.App.Tests;

/// <summary>Finds files in shared/, which the App project copies next to its binaries.</summary>
internal static class SharedFiles
{
    public static string Root { get; } = Path.Combine(AppContext.BaseDirectory, "shared");

    public static string PathOf(string relative) =>
        Path.Combine(Root, relative.Replace('/', Path.DirectorySeparatorChar));

    public static string ReadText(string relative) => File.ReadAllText(PathOf(relative));
}
