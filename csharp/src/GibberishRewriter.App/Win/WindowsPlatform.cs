using System.Diagnostics;
using GibberishRewriter.Core;
using static GibberishRewriter.App.Win.NativeMethods;
using Shortcut = GibberishRewriter.Core.Shortcut;

namespace GibberishRewriter.App.Win;

/// <summary><see cref="IPlatform"/> on Windows for one Engine and its layout pair. Called on the action thread.</summary>
internal sealed class WindowsPlatform(
    LayoutPair pair,
    InputSender sender,
    ClipboardService clipboard,
    LayoutSwitcher switcher,
    KeyStateTracker keys,
    Action<string> notify) : IPlatform
{
    public const int ReleasePollMs = 10;

    public bool WaitForRelease(IReadOnlyCollection<int> vks, int timeoutMs)
    {
        var clock = Stopwatch.StartNew();
        while (vks.Any(IsDown))
        {
            if (clock.ElapsedMilliseconds >= timeoutMs)
            {
                return false;
            }
            Thread.Sleep(ReleasePollMs);
        }
        return true;
    }

    public void SendBackspaces(int count) => sender.Backspaces(count);

    public void TypeText(string text) => sender.Text(text);

    public void SendShortcut(Shortcut shortcut) =>
        sender.Shortcut(shortcut, Foreground.IsConsoleClass(Foreground.ClassNameOf(GetForegroundWindow())));

    public object SaveClipboard() => clipboard.Save();

    public void RestoreClipboard(object saved) => clipboard.Restore(saved);

    public uint ClipboardSequence() => clipboard.Sequence();

    public string? ReadClipboardText() => clipboard.ReadText();

    public void SetClipboardText(string text) => clipboard.SetText(text);

    public void SwitchLayout(LayoutKind layout) => switcher.Switch(pair.HklOf(layout));

    public ForegroundWindow ForegroundInfo() => Foreground.Read(pair);

    public void Sleep(int milliseconds) => Thread.Sleep(milliseconds);

    public void Notify(string message) => notify(message);

    /// <summary>Swallowed keys show only in the hook's tracker; other keys show in Windows' key state too.</summary>
    private bool IsDown(int vk) => keys.IsDown(vk) || GetAsyncKeyState(vk) < 0;
}
