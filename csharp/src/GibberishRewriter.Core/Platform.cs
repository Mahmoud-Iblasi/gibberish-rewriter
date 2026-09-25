namespace GibberishRewriter.Core;

/// <summary>Shortcuts Engine sends. The platform picks console variants.</summary>
public enum Shortcut
{
    Copy,
    Paste,
    Undo,
}

/// <summary>The foreground window when an action runs. <see cref="Layout"/> is null outside the pair.</summary>
public readonly record struct ForegroundWindow(long Window, LayoutKind? Layout, bool IsConsole, bool IsBlockedByElevation);

/// <summary>Thrown by clipboard calls when another app keeps the clipboard open after every retry.</summary>
public sealed class ClipboardUnavailableException(string message) : Exception(message);

/// <summary>Everything Engine asks of Windows. Called only from the action thread.</summary>
public interface IPlatform
{
    /// <summary>Waits until none of the keys is physically down. False if one still is after the timeout. CapsLock and
    /// the trigger are swallowed, so Windows' key state never shows them down: the platform tracks them from the hook.</summary>
    bool WaitForRelease(IReadOnlyCollection<int> vks, int timeoutMs);

    void SendBackspaces(int count);

    void TypeText(string text);

    void SendShortcut(Shortcut shortcut);

    object SaveClipboard();

    void RestoreClipboard(object saved);

    uint ClipboardSequence();

    string? ReadClipboardText();

    void SetClipboardText(string text);

    void SwitchLayout(LayoutKind layout);

    ForegroundWindow ForegroundInfo();

    void Sleep(int milliseconds);

    void Notify(string message);
}

/// <summary>Notification texts shared by both apps.</summary>
public static class Messages
{
    public const string AdministratorWindow =
        "Can't fix text in an administrator window. Run Gibberish Rewriter as administrator to allow it.";

    public const string ClipboardBusy =
        "Couldn't use the clipboard because another app is holding it. Try again.";
}
