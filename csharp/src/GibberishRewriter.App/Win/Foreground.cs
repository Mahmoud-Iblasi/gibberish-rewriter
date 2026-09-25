using System.Runtime.InteropServices;
using GibberishRewriter.Core;
using static GibberishRewriter.App.Win.NativeMethods;

namespace GibberishRewriter.App.Win;

/// <summary>The foreground window, its layout, whether it is a console, and elevation.</summary>
internal static class Foreground
{
    private const int ErrorAccessDenied = 5;

    /// <summary>The classic console and Windows Terminal.</summary>
    public static bool IsConsoleClass(string className) =>
        className is "ConsoleWindowClass" or "CASCADIA_HOSTING_WINDOW_CLASS";

    public static ForegroundWindow Read(LayoutPair pair)
    {
        var window = GetForegroundWindow();
        return new ForegroundWindow(
            window.ToInt64(),
            pair.KindOf(LayoutOf(window)),
            IsConsoleClass(ClassNameOf(window)),
            IsBlockedByElevation(window));
    }

    public static IntPtr LayoutOf(IntPtr window) => GetKeyboardLayout(GetWindowThreadProcessId(window, out _));

    public static string ClassNameOf(IntPtr window)
    {
        var buffer = new char[256];
        var length = GetClassName(window, buffer, buffer.Length);
        return new string(buffer, 0, Math.Max(length, 0));
    }

    /// <summary>True when the window's process runs as administrator and this app does not. Access denied counts as elevated.</summary>
    public static bool IsBlockedByElevation(IntPtr window)
    {
        if (window == IntPtr.Zero || Environment.IsPrivilegedProcess)
        {
            return false;
        }
        GetWindowThreadProcessId(window, out var processId);
        var process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, processId);
        if (process == IntPtr.Zero)
        {
            return Marshal.GetLastPInvokeError() == ErrorAccessDenied;
        }
        try
        {
            if (!OpenProcessToken(process, TOKEN_QUERY, out var token))
            {
                return Marshal.GetLastPInvokeError() == ErrorAccessDenied;
            }
            try
            {
                return GetTokenInformation(token, TokenElevation, out var elevation, sizeof(int), out _) && elevation != 0;
            }
            finally
            {
                CloseHandle(token);
            }
        }
        finally
        {
            CloseHandle(process);
        }
    }
}
