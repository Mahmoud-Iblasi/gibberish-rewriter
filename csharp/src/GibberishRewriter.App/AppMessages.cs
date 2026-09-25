namespace GibberishRewriter.App;

/// <summary>Texts of the app's notifications and message box. The Python app uses the same texts.</summary>
internal static class AppMessages
{
    public const string Title = "Gibberish Rewriter";

    public const string Tooltip = "Gibberish Rewriter (C#)";

    public const string AlreadyRunning =
        "Gibberish Rewriter is already running (C# or Python version). Exit it from its tray icon first.";

    public const string LayoutsNotFound =
        "Couldn't find exactly one Latin and one Arabic keyboard layout. Set \"layouts\" in the config file to HKL values "
        + "such as \"04090409\" and \"04012C01\". Gibberish Rewriter stays disabled until then.";

    public const string LayoutsSame =
        "layouts.latin and layouts.arabic are the same layout. Gibberish Rewriter stays disabled until they differ.";

    public static string LayoutNotInstalled(string hkl) =>
        $"The keyboard layout {hkl} in the config file isn't installed. Gibberish Rewriter stays disabled until it is.";

    public static string LayoutHasDeadKeys(string hkl) =>
        $"The keyboard layout {hkl} has dead keys, which Gibberish Rewriter doesn't support. Gibberish Rewriter stays disabled.";

    /// <summary>Shown on every successful start, so a start that produced no tray icon is obvious.</summary>
    public static string Started(string latinHkl, string arabicHkl, string fixTyped, string fixSelection) =>
        $"Gibberish Rewriter is running. Layouts {latinHkl} and {arabicHkl}. "
        + $"{fixTyped} fixes what you just typed, {fixSelection} fixes the selected text.";

    /// <summary>The app can't start without its shared files, so it says which folder it looked in.</summary>
    public static string SharedFilesUnreadable(string sharedFolder, string detail) =>
        $"Gibberish Rewriter can't start: it couldn't read its files in{Environment.NewLine}{sharedFolder}"
        + $"{Environment.NewLine}{Environment.NewLine}{detail}{Environment.NewLine}{Environment.NewLine}"
        + "Copy the whole \"shared\" folder next to the program and start it again.";

    public static string ConfigInvalid(string code, string message) =>
        $"The config file has an error, so the last good settings stay in use. {code}: {message}";
}
