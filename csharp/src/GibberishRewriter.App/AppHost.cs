using System.Diagnostics;
using GibberishRewriter.App.Win;
using GibberishRewriter.Core;
using Microsoft.Win32;

namespace GibberishRewriter.App;

/// <summary>Starts everything, reloads the config, and answers the tray. UI thread.</summary>
internal sealed class AppHost : IDisposable
{
    private readonly AppLog _log;
    private readonly KeyNames _names;
    private readonly WordList _words;
    private readonly ConfigParser _parser;
    private readonly ConfigFile _configFile;
    private readonly Autostart _autostart;
    private readonly Tray _tray;
    private readonly SynchronizationContext _ui;
    private readonly ClipboardOwnerWindow _clipboardOwner = new();
    private readonly KeyStateTracker _keys = new();
    private readonly HookActivity _activity = new();
    private readonly InputSender _sender;
    private readonly ClipboardService _clipboard;
    private readonly LayoutSwitcher _switcher;
    private readonly ActionWorker _worker;
    private readonly HookThread _hooks;
    private readonly System.Windows.Forms.Timer _configTimer = new() { Interval = ConfigFile.PollIntervalMs };
    private HookWatchdog? _watchdog;
    private System.Windows.Forms.Timer? _startNoticeTimer;
    private volatile EngineSlot? _slot;
    private AppConfig _config;
    private string? _pairError;
    private bool _loaded;

    public AppHost(string sharedFolder, AppLog log)
    {
        _log = log;
        _names = KeyNames.Load(Path.Combine(sharedFolder, "keys.json"));
        _words = WordList.Load(Path.Combine(sharedFolder, "wordlists", "english.txt"));
        var defaultText = File.ReadAllText(Path.Combine(sharedFolder, "config.default.json"));
        _parser = new ConfigParser(_names, defaultText);
        _config = _parser.Defaults;
        _configFile = new ConfigFile(ConfigFile.DefaultPath);
        _configFile.EnsureExists(defaultText);
        _autostart = new Autostart(Environment.ProcessPath!);
        _tray = new Tray(Path.Combine(sharedFolder, "icons"));
        _ui = new WindowsFormsSynchronizationContext();

        _sender = new InputSender(_log.Write);
        _clipboard = new ClipboardService(() => _clipboardOwner.Handle, _log.Write, Thread.Sleep);
        _switcher = new LayoutSwitcher(_sender, _log.Write, Thread.Sleep);
        _worker = new ActionWorker(_log.Write);
        _hooks = new HookThread(
            new KeyboardHook(() => _slot, _sender, _keys, _activity, _log.Write),
            new MouseHook(() => _slot, _activity, _log.Write),
            _activity,
            OnHooksReinstalled,
            _log.Write);

        _tray.EnabledClicked += OnEnabledClicked;
        _tray.OpenConfigClicked += () => Process.Start(new ProcessStartInfo(_configFile.FilePath) { UseShellExecute = true });
        _tray.AutostartClicked += OnAutostartClicked;
        _tray.ExitClicked += () => ExitRequested?.Invoke();
        _configTimer.Tick += (_, _) => Load(_configFile.ReadIfChanged());
        SystemEvents.SessionSwitch += OnSessionSwitch;
    }

    public event Action? ExitRequested;

    public void Start()
    {
        _log.Write("Starting");
        Load(_configFile.ReadIfChanged());
        _hooks.Start();
        _watchdog = new HookWatchdog(
            _activity,
            () => Foreground.IsBlockedByElevation(NativeMethods.GetForegroundWindow()),
            () => Foreground.ClassNameOf(NativeMethods.GetForegroundWindow()),
            _hooks.Reinstall,
            _log.Write);
        _configTimer.Start();
        if (_slot is { } slot)
        {
            // A start with no notification and no tray icon is the failure this makes visible.
            ShowStartNotice(AppMessages.Started(
                Hkl.Format(slot.Pair.Latin),
                Hkl.Format(slot.Pair.Arabic),
                _config.FixTyped.Format(_names),
                _config.FixSelection.Format(_names)));
        }
    }

    private void ShowStartNotice(string message)
    {
        var waited = 0;
        if (TryShow())
        {
            return;
        }
        var timer = new System.Windows.Forms.Timer { Interval = StartNotice.PollIntervalMs };
        timer.Tick += (_, _) =>
        {
            waited += StartNotice.PollIntervalMs;
            if (TryShow())
            {
                timer.Dispose();
                _startNoticeTimer = null;
            }
        };
        _startNoticeTimer = timer;
        timer.Start();

        bool TryShow()
        {
            if (!StartNotice.ShouldShow(StartNotice.TaskbarExists(), StartNotice.NotificationState(), waited))
            {
                return false;
            }
            _tray.Notify(message);
            _log.Write(waited == 0 ? "Showed the start notification" : $"Showed the start notification after {waited} ms");
            return true;
        }
    }

    public void Dispose()
    {
        SystemEvents.SessionSwitch -= OnSessionSwitch;
        _configTimer.Dispose();
        _startNoticeTimer?.Dispose();
        _watchdog?.Dispose();
        _hooks.Dispose();
        SetSlot(null);
        _worker.Dispose();
        _tray.Dispose();
        _clipboardOwner.Dispose();
        _log.Write("Exited");
    }

    /// <summary>Applies config text (null: unchanged) and resolves the layout pair. An invalid file keeps
    /// the last good config; at startup that is the defaults.</summary>
    private void Load(string? text)
    {
        if (text is null && _loaded)
        {
            return;
        }
        if (text is not null)
        {
            var result = _parser.Parse(text);
            if (result.Error is { } error)
            {
                _log.Write($"Config error {error.Code}");
                _tray.Notify(AppMessages.ConfigInvalid(error.Code, error.Message));
                if (_loaded)
                {
                    return;
                }
            }
            else
            {
                _config = result.Config!;
                _log.Write("Config loaded");
            }
        }
        _loaded = true;

        var resolution = LayoutPairResolver.Resolve(_config.LatinLayout, _config.ArabicLayout, LayoutReader.InstalledWithKeyA());
        if (resolution.Pair is not { } pair)
        {
            Disable(resolution.Error!);
        }
        else if (_slot is { } current && current.Pair == pair)
        {
            current.Engine.ApplyConfig(_config);
        }
        else
        {
            try
            {
                SetSlot(BuildSlot(pair));
                _pairError = null;
                _log.Write($"Layout pair {Hkl.Format(pair.Latin)} and {Hkl.Format(pair.Arabic)}");
            }
            catch (DeadKeyException exception)
            {
                Disable(AppMessages.LayoutHasDeadKeys(Hkl.Format(exception.Layout)));
            }
        }
        UpdateTray();
    }

    private EngineSlot BuildSlot(LayoutPair pair)
    {
        var table = LayoutReader.ReadTable(_names, pair);
        var platform = new WindowsPlatform(pair, _sender, _clipboard, _switcher, _keys, NotifyFromAnyThread);
        Engine? engine = null;
        engine = new Engine(
            _names,
            table,
            new TextConverter(table, _words),
            _config,
            platform,
            action => _worker.Enqueue(engine!, action),
            CapsLockState.IsOn());
        return new EngineSlot(engine, pair);
    }

    /// <summary>Swaps the Engine the hooks feed. The old one is disabled, which clears its run.</summary>
    private void SetSlot(EngineSlot? slot)
    {
        var old = _slot;
        _slot = slot;
        if (old is not null)
        {
            old.Engine.Enabled = false;
        }
    }

    private void Disable(string error)
    {
        SetSlot(null);
        _pairError = error;
        _log.Write("No usable layout pair; disabled");
        _tray.Notify(error);
    }

    private void UpdateTray() => _tray.Show(_slot?.Engine.Enabled ?? false, _autostart.IsEnabled);

    private void NotifyFromAnyThread(string message)
    {
        _log.Write($"Notification: {message}");
        _ui.Post(_ => _tray.Notify(message), null);
    }

    private void OnEnabledClicked()
    {
        if (_slot is not { } slot)
        {
            if (_pairError is not null)
            {
                _tray.Notify(_pairError);
            }
            return;
        }
        slot.Engine.Enabled = !slot.Engine.Enabled;
        _log.Write(slot.Engine.Enabled ? "Enabled from the tray" : "Disabled from the tray");
        UpdateTray();
    }

    private void OnAutostartClicked()
    {
        try
        {
            if (_autostart.IsEnabled)
            {
                _autostart.Disable();
            }
            else
            {
                _autostart.Enable();
            }
        }
        catch (Exception exception) when (exception is UnauthorizedAccessException or System.Security.SecurityException or IOException)
        {
            _log.Write($"Start with Windows failed: {exception.GetType().Name}");
        }
        UpdateTray();
    }

    /// <summary>Hook thread. The hooks may have missed key events while they were gone.</summary>
    private void OnHooksReinstalled()
    {
        _keys.Clear();
        _slot?.Engine.ResetAfterMissedInput(CapsLockState.IsOn());
    }

    private void OnSessionSwitch(object? sender, SessionSwitchEventArgs e)
    {
        if (e.Reason != SessionSwitchReason.SessionUnlock)
        {
            return;
        }
        _keys.Clear();
        _slot?.Engine.ResetAfterMissedInput(CapsLockState.IsOn());
        _log.Write("Session unlocked");
    }
}
