namespace GibberishRewriter.App.Win;

/// <summary>Which keys are physically down, as the keyboard hook saw them. Windows' own key state never shows swallowed
/// keys (CapsLock, a chord's trigger), so WaitForRelease checks this too.</summary>
internal sealed class KeyStateTracker
{
    private readonly bool[] _down = new bool[256];

    public void Set(int vk, bool down)
    {
        if ((uint)vk < (uint)_down.Length)
        {
            _down[vk] = down;
        }
    }

    public bool IsDown(int vk) => (uint)vk < (uint)_down.Length && _down[vk];

    /// <summary>After a hook reinstall or an unlock, when key-ups may have been missed.</summary>
    public void Clear() => Array.Clear(_down);
}
