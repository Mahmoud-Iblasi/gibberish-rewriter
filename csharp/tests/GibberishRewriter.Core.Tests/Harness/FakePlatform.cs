namespace GibberishRewriter.Core.Tests.Harness;

/// <summary>A scripted platform that records the calls vectors can expect (plan Task 10, vector harness rules).</summary>
internal sealed class FakePlatform : IPlatform
{
    private uint _clipboardSequence = 1;

    public List<string> Calls { get; } = [];

    public long Window { get; set; } = 1;
    public LayoutKind? Layout { get; set; } = LayoutKind.Latin;
    public bool IsConsole { get; set; }
    public bool IsBlockedByElevation { get; set; }

    /// <summary>What WaitForRelease returns. False means the chord keys were held too long.</summary>
    public bool ReleaseInTime { get; set; } = true;

    /// <summary>Runs once, inside the next WaitForRelease: events that arrive while an action runs.</summary>
    public Action? DuringAction { get; set; }

    public string? ClipboardText { get; set; }

    /// <summary>The text a copy puts on the clipboard; null when nothing is selected.</summary>
    public string? Selection { get; set; }

    /// <summary>"save" or "set": that clipboard call throws <see cref="ClipboardUnavailableException"/>.</summary>
    public string? ClipboardLocked { get; set; }

    public bool WaitForRelease(IReadOnlyCollection<int> vks, int timeoutMs)
    {
        var during = DuringAction;
        DuringAction = null;
        during?.Invoke();
        return ReleaseInTime;
    }

    public void SendBackspaces(int count) => Calls.Add($"backspaces {count}");

    public void TypeText(string text) => Calls.Add($"type {text}");

    public void SendShortcut(Shortcut shortcut)
    {
        Calls.Add($"shortcut {shortcut.ToString().ToLowerInvariant()}");
        if (shortcut == Shortcut.Copy && Selection is not null)
        {
            ClipboardText = Selection;
            _clipboardSequence++;
        }
    }

    public object SaveClipboard() =>
        ClipboardLocked == "save" ? throw new ClipboardUnavailableException("locked") : new SavedClipboard(ClipboardText);

    public void RestoreClipboard(object saved)
    {
        ClipboardText = ((SavedClipboard)saved).Text;
        _clipboardSequence++;
        Calls.Add($"restoreClipboard {ClipboardText}");
    }

    public uint ClipboardSequence() => _clipboardSequence;

    public string? ReadClipboardText() => ClipboardText;

    public void SetClipboardText(string text)
    {
        if (ClipboardLocked == "set")
        {
            throw new ClipboardUnavailableException("locked");
        }
        ClipboardText = text;
        _clipboardSequence++;
        Calls.Add($"setClipboard {text}");
    }

    public void SwitchLayout(LayoutKind layout)
    {
        Layout = layout;
        Calls.Add($"switchLayout {layout.ToName()}");
    }

    public ForegroundWindow ForegroundInfo() => new(Window, Layout, IsConsole, IsBlockedByElevation);

    public void Sleep(int milliseconds)
    {
    }

    public void Notify(string message) => Calls.Add($"notify {message}");

    private sealed record SavedClipboard(string? Text);
}
