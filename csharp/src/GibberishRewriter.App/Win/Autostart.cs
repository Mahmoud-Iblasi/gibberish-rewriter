using Microsoft.Win32;

namespace GibberishRewriter.App.Win;

/// <summary>The GibberishRewriter value under HKCU\Software\Microsoft\Windows\CurrentVersion\Run.</summary>
internal sealed class Autostart(string exePath)
{
    public const string RunKey = @"Software\Microsoft\Windows\CurrentVersion\Run";
    public const string ValueName = "GibberishRewriter";

    /// <summary>True when the registry value starts this app.</summary>
    public bool IsEnabled
    {
        get
        {
            using var key = Registry.CurrentUser.OpenSubKey(RunKey);
            return PointsAt(key?.GetValue(ValueName) as string, exePath);
        }
    }

    public static string CommandFor(string exePath) => $"\"{exePath}\"";

    /// <summary>True when <paramref name="command"/> starts this exe, in any letter case. A Run value may carry
    /// arguments — the Python app's is a quoted interpreter path followed by <c>-m gibberish_rewriter</c> — so a
    /// quoted value is compared up to its closing quote. An unquoted value is compared whole first, because a path
    /// with spaces and no arguments is written that way, and only then up to its first space.</summary>
    public static bool PointsAt(string? command, string exePath)
    {
        if (command is null)
        {
            return false;
        }
        var text = command.Trim();
        if (text.StartsWith('"'))
        {
            var close = text.IndexOf('"', 1);
            return Same(close < 0 ? text[1..] : text[1..close], exePath);
        }
        var space = text.IndexOf(' ');
        return Same(text, exePath) || (space > 0 && Same(text[..space], exePath));
    }

    private static bool Same(string left, string right) => string.Equals(left, right, StringComparison.OrdinalIgnoreCase);

    /// <summary>Writes this exe's path, replacing a value the Python app wrote.</summary>
    public void Enable()
    {
        using var key = Registry.CurrentUser.CreateSubKey(RunKey);
        key.SetValue(ValueName, CommandFor(exePath));
    }

    public void Disable()
    {
        using var key = Registry.CurrentUser.OpenSubKey(RunKey, writable: true);
        key?.DeleteValue(ValueName, throwOnMissingValue: false);
    }
}
