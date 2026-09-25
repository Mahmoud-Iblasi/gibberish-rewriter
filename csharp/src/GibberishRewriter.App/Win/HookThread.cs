using System.Runtime.InteropServices;
using static GibberishRewriter.App.Win.NativeMethods;

namespace GibberishRewriter.App.Win;

/// <summary>One thread installs both hooks and runs a message loop and nothing else, so a busy UI never
/// delays a hook past Windows' timeout.</summary>
internal sealed class HookThread : IDisposable
{
    private const uint WmReinstall = WM_APP + 1;

    private readonly KeyboardHook _keyboard;
    private readonly MouseHook _mouse;
    private readonly HookActivity _activity;
    private readonly Action _reinstalled;
    private readonly Action<string> _log;
    private readonly Thread _thread;
    private readonly ManualResetEventSlim _ready = new();
    private uint _threadId;

    /// <param name="reinstalled">Runs on the hook thread after a reinstall. Keep it quick.</param>
    public HookThread(KeyboardHook keyboard, MouseHook mouse, HookActivity activity, Action reinstalled, Action<string> log)
    {
        _keyboard = keyboard;
        _mouse = mouse;
        _activity = activity;
        _reinstalled = reinstalled;
        _log = log;
        _thread = new Thread(Run) { Name = "Hooks", IsBackground = true, Priority = ThreadPriority.AboveNormal };
    }

    /// <summary>Starts the thread and returns once both hooks are installed.</summary>
    public void Start()
    {
        _thread.Start();
        _ready.Wait();
    }

    /// <summary>Any thread. Reinstalls both hooks on the hook thread.</summary>
    public void Reinstall() => PostThreadMessage(_threadId, WmReinstall, UIntPtr.Zero, IntPtr.Zero);

    public void Dispose()
    {
        if (_thread.IsAlive)
        {
            PostThreadMessage(_threadId, WM_QUIT, UIntPtr.Zero, IntPtr.Zero);
            _thread.Join(2000);
        }
        _ready.Dispose();
    }

    private void Run()
    {
        _threadId = GetCurrentThreadId();
        // Creates the thread's message queue, so PostThreadMessage works from the first moment.
        PeekMessage(out _, IntPtr.Zero, WM_USER, WM_USER, PM_NOREMOVE);
        Install();
        _ready.Set();

        while (true)
        {
            var result = GetMessage(out var message, IntPtr.Zero, 0, 0);
            if (result == 0)
            {
                break;
            }
            if (result == -1)
            {
                // The hooks live and die with this loop, and the watchdog's reinstall message would go
                // to a thread that is gone. Leaving without a word is the one failure that looks like a Windows bug.
                _log($"Hook message loop failed with error {Marshal.GetLastPInvokeError()}; the hooks are gone");
                break;
            }
            if (message.message != WmReinstall)
            {
                continue;
            }
            try
            {
                Uninstall();
                Install();
                _reinstalled();
            }
            catch (Exception exception)
            {
                // An exception escaping the hook thread would end the process.
                _log($"Hook reinstall error: {exception.GetType().Name}");
            }
        }
        Uninstall();
    }

    private void Install()
    {
        _activity.Note(HookWatchdog.LastInputTime() ?? 0);
        _keyboard.Install();
        _mouse.Install();
    }

    private void Uninstall()
    {
        _keyboard.Uninstall();
        _mouse.Uninstall();
    }
}
