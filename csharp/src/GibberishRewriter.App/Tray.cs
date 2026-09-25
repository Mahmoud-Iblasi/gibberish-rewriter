namespace GibberishRewriter.App;

/// <summary>The tray icon, its menu and notifications. UI thread only.</summary>
internal sealed class Tray : IDisposable
{
    private const int MaxNotificationLength = 255;

    private readonly NotifyIcon _icon;
    private readonly Icon _enabledIcon;
    private readonly Icon _disabledIcon;
    private readonly ToolStripMenuItem _enabled;
    private readonly ToolStripMenuItem _autostart;

    public Tray(string iconsFolder)
    {
        _enabledIcon = new Icon(Path.Combine(iconsFolder, "tray.ico"), SystemInformation.SmallIconSize);
        _disabledIcon = new Icon(Path.Combine(iconsFolder, "tray-disabled.ico"), SystemInformation.SmallIconSize);
        _enabled = new ToolStripMenuItem("Enabled", null, (_, _) => EnabledClicked?.Invoke());
        _autostart = new ToolStripMenuItem("Start with Windows", null, (_, _) => AutostartClicked?.Invoke());
        var menu = new ContextMenuStrip();
        menu.Items.AddRange(
        [
            _enabled,
            new ToolStripMenuItem("Open config file", null, (_, _) => OpenConfigClicked?.Invoke()),
            _autostart,
            new ToolStripMenuItem("Exit", null, (_, _) => ExitClicked?.Invoke()),
        ]);
        _icon = new NotifyIcon { Text = AppMessages.Tooltip, Icon = _disabledIcon, ContextMenuStrip = menu, Visible = true };
    }

    public event Action? EnabledClicked;
    public event Action? OpenConfigClicked;
    public event Action? AutostartClicked;
    public event Action? ExitClicked;

    public void Show(bool enabled, bool autostart)
    {
        _enabled.Checked = enabled;
        _autostart.Checked = autostart;
        _icon.Icon = enabled ? _enabledIcon : _disabledIcon;
    }

    public void Notify(string message) =>
        _icon.ShowBalloonTip(
            5000,
            AppMessages.Title,
            message.Length <= MaxNotificationLength ? message : message[..(MaxNotificationLength - 3)] + "...",
            ToolTipIcon.Info);

    public void Dispose()
    {
        _icon.Visible = false;
        _icon.ContextMenuStrip?.Dispose();
        _icon.Dispose();
        _enabledIcon.Dispose();
        _disabledIcon.Dispose();
    }
}
