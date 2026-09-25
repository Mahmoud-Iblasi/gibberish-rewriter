using static GibberishRewriter.App.Win.NativeMethods;

namespace GibberishRewriter.App.Win;

/// <summary>The start notification waits until Windows can show it. Started at sign-in, the app can come
/// up before the taskbar exists or while Windows holds notifications back, and a balloon shown then is lost.</summary>
internal static class StartNotice
{
    public const int PollIntervalMs = 500;
    public const int MaxWaitMs = 60_000;

    /// <summary>True once the taskbar exists and Windows accepts notifications, or after <see cref="MaxWaitMs"/>,
    /// so a Windows that never reports ready still gets the attempt.</summary>
    public static bool ShouldShow(bool taskbarExists, int notificationState, int waitedMs) =>
        waitedMs >= MaxWaitMs || (taskbarExists && notificationState == QUNS_ACCEPTS_NOTIFICATIONS);

    public static bool TaskbarExists() => FindWindow("Shell_TrayWnd", null) != IntPtr.Zero;

    /// <summary>SHQueryUserNotificationState's QUNS value, or 0 if the call fails.</summary>
    public static int NotificationState() => SHQueryUserNotificationState(out var state) == 0 ? state : 0;
}
