using static GibberishRewriter.App.Win.NativeMethods;

namespace GibberishRewriter.App.Win;

/// <summary>Asks the foreground window to switch layout, and falls back to Win+Space.</summary>
internal sealed class LayoutSwitcher(InputSender sender, Action<string> log, Action<int> sleep)
{
    public const int CheckDelayMs = 200;

    /// <summary>Win+Space cycles through the layouts, so it reaches the target for sure only when exactly two are installed.</summary>
    public static bool NeedsWinSpace(uint current, uint target, int installedCount) =>
        current != target && installedCount == 2;

    public void Switch(uint target)
    {
        PostMessage(GetForegroundWindow(), WM_INPUTLANGCHANGEREQUEST, IntPtr.Zero, Hkl.ToHandle(target));
        sleep(CheckDelayMs);
        var current = Hkl.Low32(Foreground.LayoutOf(GetForegroundWindow()));
        if (current == target)
        {
            log($"Switched the layout to {Hkl.Format(target)}");
        }
        else if (NeedsWinSpace(current, target, GetKeyboardLayoutList(0, null)))
        {
            sender.WinSpace();
            log($"The layout stayed {Hkl.Format(current)}; sent Win+Space");
        }
        else
        {
            log($"The layout stayed {Hkl.Format(current)}; couldn't switch to {Hkl.Format(target)}");
        }
    }
}
