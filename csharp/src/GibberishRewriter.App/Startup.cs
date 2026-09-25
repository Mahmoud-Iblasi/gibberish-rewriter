namespace GibberishRewriter.App;

/// <summary>Telling a file in <c>shared/</c> the app can't read apart from a bug in the app.</summary>
internal static class Startup
{
    /// <summary>True for what reading <c>shared/</c> throws: a missing folder or file and an unreadable one
    /// (<see cref="IOException"/>, <see cref="UnauthorizedAccessException"/>), and the <see cref="ArgumentException"/>
    /// the <c>Icon</c> constructor throws for a file that is not an icon. A bad argument from our own code is a bug,
    /// not a missing file, so those two stay out.</summary>
    public static bool IsSharedFileProblem(Exception exception) =>
        exception is IOException or UnauthorizedAccessException
        || (exception is ArgumentException and not (ArgumentNullException or ArgumentOutOfRangeException));
}
