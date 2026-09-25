namespace GibberishRewriter.Core;

/// <summary>One low-level key event.</summary>
/// <param name="Modifiers">Shift, Ctrl, Alt and Win as Windows reports them just before this event.</param>
/// <param name="Layout">The foreground layout, or null when it isn't one of the pair.</param>
public readonly record struct KeyEvent(
    int Vk,
    bool Down,
    bool InjectedBySelf,
    bool IsPacket,
    HoldKeys Modifiers,
    long Window,
    LayoutKind? Layout);

/// <summary>Whether to swallow a key event, and keys to press right away.</summary>
public readonly record struct KeyDecision(bool Swallow, IReadOnlyList<int> SendKeys)
{
    public static KeyDecision Pass { get; } = new(false, Array.Empty<int>());
}

/// <summary>Joins the Core modules: decides pass or swallow, records the run, and runs actions through <see cref="IPlatform"/>.</summary>
public sealed class Engine
{
    private const int ClipboardPollMs = 20;

    private readonly object _lock = new();
    private readonly KeyNames _names;
    private readonly KeyTable _table;
    private readonly TextConverter _converter;
    private readonly IPlatform _platform;
    private readonly Action<ChordAction> _startAction;
    private readonly ChordDetector _chords;
    private readonly TypingRun _run;
    private AppConfig _config;
    private bool _enabled;
    private bool _capsLockOn;
    private bool _capsLockDownWhileDisabled;
    private bool _busy;
    private bool _breakDuringAction;
    private SelectionFix? _lastSelectionFix;

    /// <param name="startAction">Called outside the lock when a chord fires. The host calls <see cref="RunAction"/> exactly once for each call, on its one worker thread.</param>
    /// <param name="capsLockOn">The Caps Lock toggle as Windows reports it at startup.</param>
    public Engine(
        KeyNames names,
        KeyTable table,
        TextConverter converter,
        AppConfig config,
        IPlatform platform,
        Action<ChordAction> startAction,
        bool capsLockOn)
    {
        _names = names;
        _table = table;
        _converter = converter;
        _config = config;
        _platform = platform;
        _startAction = startAction;
        _capsLockOn = capsLockOn;
        _enabled = config.Enabled;
        _chords = new ChordDetector(names, config.FixTyped, config.FixSelection);
        _run = new TypingRun(config.MaxRunLength);
    }

    public bool Enabled
    {
        get
        {
            lock (_lock)
            {
                return _enabled;
            }
        }
        set
        {
            lock (_lock)
            {
                if (value == _enabled)
                {
                    return;
                }
                _enabled = value;
                _capsLockDownWhileDisabled = false;
                _chords.SetChords(_config.FixTyped, _config.FixSelection);
                Break();
            }
        }
    }

    /// <summary>A reloaded config. A chord being pressed is forgotten only when a hotkey changed.</summary>
    public void ApplyConfig(AppConfig config)
    {
        lock (_lock)
        {
            if (config.FixTyped != _config.FixTyped || config.FixSelection != _config.FixSelection)
            {
                _chords.SetChords(config.FixTyped, config.FixSelection);
            }
            _config = config;
            _run.MaxLength = config.MaxRunLength;
        }
        Enabled = config.Enabled;
    }

    /// <summary>Hook thread. Decides one key event.</summary>
    public KeyDecision OnKey(KeyEvent e)
    {
        KeyDecision decision;
        ChordAction? start;
        lock (_lock)
        {
            decision = Decide(e, out start);
        }
        if (start is { } action)
        {
            _startAction(action);
        }
        return decision;
    }

    /// <summary>Hook thread. Any mouse button press is a break.</summary>
    public void OnMouseDown()
    {
        lock (_lock)
        {
            if (_enabled)
            {
                Break();
            }
        }
    }

    /// <summary>Any thread. Corrects the tracked Caps Lock toggle when Windows may have changed it without the hook
    /// seeing a key (after the lock screen or a UAC prompt, or after a hook was reinstalled).</summary>
    public void SetCapsLockOn(bool capsLockOn)
    {
        lock (_lock)
        {
            _capsLockOn = capsLockOn;
        }
    }

    /// <summary>Any thread. After a hook reinstall or a session unlock, when the hooks may have missed key events:
    /// takes the Caps Lock toggle Windows reports, forgets a half-pressed chord, and breaks the run.</summary>
    public void ResetAfterMissedInput(bool capsLockOn)
    {
        lock (_lock)
        {
            _capsLockOn = capsLockOn;
            _capsLockDownWhileDisabled = false;
            _chords.SetChords(_config.FixTyped, _config.FixSelection);
            Break();
        }
    }

    /// <summary>Worker thread. Runs the action <c>startAction</c> asked for. Platform exceptions other than
    /// <see cref="ClipboardUnavailableException"/> propagate; the host logs them.</summary>
    public void RunAction(ChordAction action)
    {
        try
        {
            AppConfig config;
            lock (_lock)
            {
                config = _config;
            }
            var chord = action == ChordAction.FixTyped ? config.FixTyped : config.FixSelection;
            if (!_platform.WaitForRelease(ReleaseKeys(chord), config.ReleaseTimeoutMs))
            {
                return;
            }
            lock (_lock)
            {
                // A key or click while the chord keys were still held has already reached the app, so the run
                // and any selection no longer match the screen: cancel. EndAction's deferred break clears both.
                if (_breakDuringAction)
                {
                    return;
                }
            }
            if (action == ChordAction.FixTyped)
            {
                FixTyped(config);
                return;
            }
            try
            {
                FixSelection(config);
            }
            finally
            {
                lock (_lock)
                {
                    _run.Clear();
                }
            }
        }
        finally
        {
            EndAction();
        }
    }

    private KeyDecision Decide(KeyEvent e, out ChordAction? start)
    {
        start = null;
        if (e.InjectedBySelf)
        {
            return KeyDecision.Pass;
        }
        if (!_enabled)
        {
            TrackCapsLockWhileDisabled(e);
            return KeyDecision.Pass;
        }
        if (e.IsPacket)
        {
            if (e.Down)
            {
                Break();
            }
            return KeyDecision.Pass;
        }

        var chord = _chords.OnKey(e.Vk, e.Down, e.Modifiers);
        if (chord.CapsLockToggled)
        {
            _capsLockOn = !_capsLockOn;
        }
        if (chord.Fired is { } fired && !_busy)
        {
            _busy = true;
            start = fired;
        }
        if (chord.Swallow)
        {
            var send = new List<int>(2);
            if (chord.ReplayCapsLock)
            {
                send.Add(KeyNames.VkCapsLock);
            }
            if (chord.SendMaskKey)
            {
                send.Add(KeyNames.VkMask);
            }
            return new KeyDecision(true, send);
        }
        if (e.Down)
        {
            OnPassedKeyDown(e);
        }
        return KeyDecision.Pass;
    }

    /// <summary>Records the key or breaks the run, for a key-down that reaches Windows.</summary>
    private void OnPassedKeyDown(KeyEvent e)
    {
        if (_names.IsModifier(e.Vk))
        {
            return;
        }
        if ((e.Modifiers & (HoldKeys.Ctrl | HoldKeys.Alt | HoldKeys.Win)) != 0 || _busy)
        {
            Break();
            return;
        }
        if (e.Vk == KeyNames.VkBackspace)
        {
            _lastSelectionFix = null;
            _run.Backspace(_table);
            return;
        }
        if (e.Layout is not { } layout)
        {
            Break();
            return;
        }

        var shift = (e.Modifiers & HoldKeys.Shift) != 0;
        var state = LayoutKinds.StateOf(shift, _capsLockOn);
        var text = _table.TextOf(e.Vk, layout, state);
        if (text.Length == 0)
        {
            Break();
            return;
        }
        var other = _table.TextOf(e.Vk, layout.Other(), state);
        _lastSelectionFix = null;
        _run.Record(e.Window, layout, new KeyRecord(e.Vk, shift, _capsLockOn, text, other.Length > 0 ? other : text));
    }

    private void TrackCapsLockWhileDisabled(KeyEvent e)
    {
        if (e.Vk != KeyNames.VkCapsLock)
        {
            return;
        }
        if (e.Down && !_capsLockDownWhileDisabled)
        {
            _capsLockOn = !_capsLockOn;
        }
        _capsLockDownWhileDisabled = e.Down;
    }

    /// <summary>Clears the run and forgets the last selection fix, or marks both for when the running action ends.</summary>
    private void Break()
    {
        if (_busy)
        {
            _breakDuringAction = true;
            return;
        }
        _run.Clear();
        _lastSelectionFix = null;
    }

    private int[] ReleaseKeys(Chord chord) => _names.VksOf(chord.Hold).Append(chord.TriggerVk).ToArray();

    private void EndAction()
    {
        lock (_lock)
        {
            _busy = false;
            if (_breakDuringAction)
            {
                _breakDuringAction = false;
                Break();
            }
        }
    }

    /// <summary>Fixes what was just typed. Also the undo, because the fix leaves the run describing the fixed text.</summary>
    private void FixTyped(AppConfig config)
    {
        lock (_lock)
        {
            _lastSelectionFix = null;
        }

        var foreground = _platform.ForegroundInfo();
        if (foreground.IsBlockedByElevation)
        {
            _platform.Notify(Messages.AdministratorWindow);
            return;
        }

        string text;
        string otherText;
        LayoutKind target;
        lock (_lock)
        {
            if (_run.IsEmpty || foreground.Window != _run.Window)
            {
                _run.Clear();
                return;
            }
            text = _run.Text;
            otherText = _run.OtherText;
            target = _run.Layout.Other();
        }

        _platform.SendBackspaces(text.Length);
        _platform.TypeText(otherText);
        if (config.SwitchLayoutAfterFix)
        {
            _platform.SwitchLayout(target);
        }

        lock (_lock)
        {
            _run.SwapAfterFix();
        }
    }

    /// <summary>Fixes the selected text through the clipboard. RunAction clears the run afterwards.</summary>
    private void FixSelection(AppConfig config)
    {
        SelectionFix? previous;
        lock (_lock)
        {
            previous = _lastSelectionFix;
            _lastSelectionFix = null;
        }

        var foreground = _platform.ForegroundInfo();
        if (foreground.IsBlockedByElevation)
        {
            _platform.Notify(Messages.AdministratorWindow);
            return;
        }

        if (previous is not null && previous.Window == foreground.Window && !foreground.IsConsole)
        {
            _platform.SendShortcut(Shortcut.Undo);
            if (config.SwitchLayoutAfterFix)
            {
                _platform.SwitchLayout(previous.SourceLayout);
            }
            return;
        }

        object saved;
        try
        {
            saved = _platform.SaveClipboard();
        }
        catch (ClipboardUnavailableException)
        {
            _platform.Notify(Messages.ClipboardBusy);
            return;
        }

        Conversion conversion;
        try
        {
            var sequence = _platform.ClipboardSequence();
            _platform.SendShortcut(Shortcut.Copy);
            if (!WaitForClipboardChange(sequence, config.ClipboardTimeoutMs))
            {
                return;
            }

            var copied = _platform.ReadClipboardText();
            if (copied is null || _converter.Convert(copied) is not { } converted || converted.Text == copied)
            {
                _platform.RestoreClipboard(saved);
                return;
            }

            conversion = converted;
            _platform.SetClipboardText(conversion.Text);
            _platform.SendShortcut(Shortcut.Paste);
            _platform.Sleep(config.PasteRestoreDelayMs);
            _platform.RestoreClipboard(saved);
        }
        catch (ClipboardUnavailableException)
        {
            TryRestoreClipboard(saved);
            _platform.Notify(Messages.ClipboardBusy);
            return;
        }

        if (config.SwitchLayoutAfterFix)
        {
            _platform.SwitchLayout(conversion.Target);
        }
        lock (_lock)
        {
            _lastSelectionFix = new SelectionFix(foreground.Window, conversion.Target.Other());
        }
    }

    /// <summary>True once the clipboard sequence number moves; false after the timeout (nothing was selected).</summary>
    private bool WaitForClipboardChange(uint sequence, int timeoutMs)
    {
        for (var waited = 0; ; waited += ClipboardPollMs)
        {
            if (_platform.ClipboardSequence() != sequence)
            {
                return true;
            }
            if (waited >= timeoutMs)
            {
                return false;
            }
            _platform.Sleep(ClipboardPollMs);
        }
    }

    private void TryRestoreClipboard(object saved)
    {
        try
        {
            _platform.RestoreClipboard(saved);
        }
        catch (ClipboardUnavailableException)
        {
            // Still locked. The ClipboardBusy notification that follows covers it.
        }
    }

    /// <summary>The last selection fix that pasted. <see cref="SourceLayout"/> is the layout of the text before it.</summary>
    private sealed record SelectionFix(long Window, LayoutKind SourceLayout);
}
