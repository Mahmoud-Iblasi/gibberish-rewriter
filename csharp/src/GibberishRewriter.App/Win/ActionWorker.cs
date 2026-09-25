using System.Collections.Concurrent;
using GibberishRewriter.Core;
using static GibberishRewriter.App.Win.NativeMethods;

namespace GibberishRewriter.App.Win;

/// <summary>One worker thread runs actions in order, each exactly once.</summary>
internal sealed class ActionWorker : IDisposable
{
    private readonly BlockingCollection<(Engine Engine, ChordAction Action)> _queue = new();
    private readonly Action<string> _log;
    private readonly Thread _thread;

    public ActionWorker(Action<string> log)
    {
        _log = log;
        _thread = new Thread(Run) { Name = "Actions", IsBackground = true };
        _thread.Start();
    }

    /// <summary>Hook thread, from Engine's startAction. Only queues, so the hook returns at once.</summary>
    public void Enqueue(Engine engine, ChordAction action) => _queue.Add((engine, action));

    public void Dispose()
    {
        _queue.CompleteAdding();
        if (_thread.Join(2000))
        {
            _queue.Dispose();
        }
    }

    private void Run()
    {
        foreach (var (engine, action) in _queue.GetConsumingEnumerable())
        {
            try
            {
                engine.RunAction(action);
                _log($"Ran {action}");
            }
            catch (Exception exception)
            {
                _log($"{action} failed: {exception.GetType().Name}");
            }
        }
    }
}

/// <summary>The Caps Lock toggle as Windows reports it, for Engine's SetCapsLockOn.</summary>
internal static class CapsLockState
{
    private const int VkCapital = 0x14;

    public static bool IsOn() => (GetKeyState(VkCapital) & 1) != 0;
}
