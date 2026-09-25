using System.Runtime.InteropServices;
using static GibberishRewriter.App.Win.NativeMethods;

namespace GibberishRewriter.App.Win;

/// <summary>A WH_KEYBOARD_LL or WH_MOUSE_LL hook. Install and Uninstall run on the hook thread.</summary>
internal abstract class LowLevelHook
{
    private readonly int _kind;

    // Kept in a field for the hook's lifetime, so the delegate Windows calls is never garbage-collected.
    private readonly LowLevelHookProc _callback;

    private IntPtr _handle;

    protected LowLevelHook(int kind, Action<string> log)
    {
        _kind = kind;
        _callback = Callback;
        Log = log;
    }

    protected Action<string> Log { get; }

    public void Install()
    {
        _handle = SetWindowsHookEx(_kind, _callback, GetModuleHandle(null), 0);
        if (_handle == IntPtr.Zero)
        {
            Log($"{GetType().Name} install failed (error {Marshal.GetLastPInvokeError()})");
        }
    }

    public void Uninstall()
    {
        if (_handle != IntPtr.Zero)
        {
            UnhookWindowsHookEx(_handle);
            _handle = IntPtr.Zero;
        }
    }

    /// <returns>True to swallow the event.</returns>
    protected abstract bool OnEvent(IntPtr message, IntPtr data);

    private IntPtr Callback(int code, IntPtr message, IntPtr data)
    {
        if (code == HC_ACTION)
        {
            try
            {
                if (OnEvent(message, data))
                {
                    return 1;
                }
            }
            catch (Exception exception)
            {
                // An exception escaping a hook callback would end the process.
                Log($"{GetType().Name} error: {exception.GetType().Name}");
            }
        }
        return CallNextHookEx(_handle, code, message, data);
    }
}
