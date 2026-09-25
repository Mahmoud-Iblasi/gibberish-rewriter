using System.Runtime.InteropServices;
using static GibberishRewriter.App.Win.NativeMethods;

namespace GibberishRewriter.App.Win;

/// <summary>The time of the hooks' last event, in the milliseconds hook structs and GetLastInputInfo use.</summary>
internal sealed class HookActivity
{
    private int _lastEventTime;

    public uint LastEventTime => unchecked((uint)Volatile.Read(ref _lastEventTime));

    public void Note(uint time) => Volatile.Write(ref _lastEventTime, unchecked((int)time));
}

/// <summary>Reinstalls the hooks when Windows has silently removed one.</summary>
internal sealed class HookWatchdog : IDisposable
{
    public const int IntervalMs = 5000;
    public const uint StaleAfterMs = 2000;

    private readonly HookActivity _activity;
    private readonly Func<bool> _foregroundBlockedByElevation;
    private readonly Func<string> _foregroundClass;
    private readonly Action _reinstall;
    private readonly Action<string> _log;
    private readonly System.Threading.Timer _timer;

    /// <param name="foregroundClass">The foreground window's class name, logged with a reinstall so the log shows where
    /// the missed input went.</param>
    public HookWatchdog(
        HookActivity activity,
        Func<bool> foregroundBlockedByElevation,
        Func<string> foregroundClass,
        Action reinstall,
        Action<string> log)
    {
        _activity = activity;
        _foregroundBlockedByElevation = foregroundBlockedByElevation;
        _foregroundClass = foregroundClass;
        _reinstall = reinstall;
        _log = log;
        _timer = new System.Threading.Timer(_ => Check(), null, IntervalMs, IntervalMs);
    }

    /// <summary>True when Windows saw input more than <see cref="StaleAfterMs"/> after the hooks' last event.
    /// Tick counts wrap after 49.7 days, so the gap is taken modulo 2^32 and a "negative" gap is not stale.</summary>
    public static bool IsStale(uint lastInputTime, uint lastHookTime, bool blockedByElevation)
    {
        var gap = unchecked(lastInputTime - lastHookTime);
        return !blockedByElevation && gap > StaleAfterMs && gap < 0x80000000;
    }

    public static string MissedInputMessage(uint gapMs, string foregroundClass) =>
        $"The hooks missed input for {gapMs} ms (foreground: {foregroundClass}); reinstalling them";

    /// <summary>GetLastInputInfo's time, or null if the call fails.</summary>
    public static uint? LastInputTime()
    {
        var info = new LASTINPUTINFO { cbSize = (uint)Marshal.SizeOf<LASTINPUTINFO>() };
        return GetLastInputInfo(ref info) ? info.dwTime : null;
    }

    public void Dispose() => _timer.Dispose();

    private void Check()
    {
        try
        {
            if (LastInputTime() is not { } lastInput
                || !IsStale(lastInput, _activity.LastEventTime, _foregroundBlockedByElevation()))
            {
                return;
            }
            _log(MissedInputMessage(unchecked(lastInput - _activity.LastEventTime), _foregroundClass()));
            _activity.Note(lastInput);
            _reinstall();
        }
        catch (Exception exception)
        {
            _log($"Hook watchdog error: {exception.GetType().Name}");
        }
    }
}
