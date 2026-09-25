using GibberishRewriter.App.Win;
using static GibberishRewriter.App.Win.NativeMethods;

namespace GibberishRewriter.App.Tests;

internal static class TestThreads
{
    /// <summary>Runs <paramref name="action"/> on a new STA thread, as WinForms clipboard calls need.</summary>
    public static T OnSta<T>(Func<T> action)
    {
        T result = default!;
        Exception? error = null;
        var thread = new Thread(() =>
        {
            try
            {
                result = action();
            }
            catch (Exception exception)
            {
                error = exception;
            }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();
        return error is null ? result : throw new InvalidOperationException("The STA action failed.", error);
    }
}

/// <summary>A clipboard owner window on its own thread with a message loop, like the app's UI thread.</summary>
internal sealed class OwnerThread : IDisposable
{
    private readonly Thread _thread;
    private readonly ManualResetEventSlim _ready = new();
    private ClipboardOwnerWindow? _window;
    private uint _threadId;

    public OwnerThread()
    {
        _thread = new Thread(() =>
        {
            _threadId = GetCurrentThreadId();
            _window = new ClipboardOwnerWindow();
            _ready.Set();
            Application.Run();
            _window.Dispose();
        });
        _thread.SetApartmentState(ApartmentState.STA);
        _thread.Start();
        _ready.Wait();
    }

    public IntPtr Handle => _window!.Handle;

    public void Dispose()
    {
        PostThreadMessage(_threadId, WM_QUIT, UIntPtr.Zero, IntPtr.Zero);
        _thread.Join();
        _ready.Dispose();
    }
}
