using static GibberishRewriter.App.Win.NativeMethods;
using Shortcut = GibberishRewriter.Core.Shortcut;

namespace GibberishRewriter.App.Win;

/// <summary>Builds the event arrays InputSender passes to SendInput. Pure, so it is unit-tested.</summary>
internal static class InputBuilder
{
    /// <summary>dwExtraInfo on every event this app sends ("GRWR"); KeyboardHook recognizes the app's own input by it.</summary>
    public const uint ExtraInfo = 0x47525752;

    /// <summary>SendInput is called with at most this many events at a time.</summary>
    public const int ChunkSize = 50;

    public const ushort VkBack = 0x08;
    public const ushort VkShift = 0x10;
    public const ushort VkControl = 0x11;
    public const ushort VkSpace = 0x20;
    public const ushort VkInsert = 0x2D;
    public const ushort VkC = 0x43;
    public const ushort VkV = 0x56;
    public const ushort VkZ = 0x5A;
    public const ushort VkLWin = 0x5B;

    public static INPUT Key(ushort vk, bool up) => new()
    {
        type = INPUT_KEYBOARD,
        u = new InputUnion
        {
            ki = new KEYBDINPUT
            {
                wVk = vk,
                dwFlags = (up ? KEYEVENTF_KEYUP : 0) | (IsExtended(vk) ? KEYEVENTF_EXTENDEDKEY : 0),
                dwExtraInfo = (UIntPtr)ExtraInfo,
            },
        },
    };

    public static INPUT Unicode(char c, bool up) => new()
    {
        type = INPUT_KEYBOARD,
        u = new InputUnion
        {
            ki = new KEYBDINPUT
            {
                wScan = c,
                dwFlags = KEYEVENTF_UNICODE | (up ? KEYEVENTF_KEYUP : 0),
                dwExtraInfo = (UIntPtr)ExtraInfo,
            },
        },
    };

    /// <summary>One press (down, up) of a virtual key: the CapsLock replay or the 0xE8 mask key.</summary>
    public static INPUT[] KeyPress(ushort vk) => [Key(vk, false), Key(vk, true)];

    public static INPUT[] Backspaces(int count)
    {
        var events = new INPUT[count * 2];
        for (var i = 0; i < count; i++)
        {
            events[i * 2] = Key(VkBack, false);
            events[i * 2 + 1] = Key(VkBack, true);
        }
        return events;
    }

    /// <summary>Each UTF-16 unit as a KEYEVENTF_UNICODE down and up.</summary>
    public static INPUT[] Text(string text)
    {
        var events = new INPUT[text.Length * 2];
        for (var i = 0; i < text.Length; i++)
        {
            events[i * 2] = Unicode(text[i], false);
            events[i * 2 + 1] = Unicode(text[i], true);
        }
        return events;
    }

    /// <summary>Ctrl+C / Ctrl+V / Ctrl+Z, or Ctrl+Insert / Shift+Insert in console windows.</summary>
    public static INPUT[] Shortcut(Shortcut shortcut, bool console)
    {
        var (modifier, key) = shortcut switch
        {
            Core.Shortcut.Copy => console ? (VkControl, VkInsert) : (VkControl, VkC),
            Core.Shortcut.Paste => console ? (VkShift, VkInsert) : (VkControl, VkV),
            _ => (VkControl, VkZ),
        };
        return [Key(modifier, false), Key(key, false), Key(key, true), Key(modifier, true)];
    }

    /// <summary>Win+Space, the layout-switch fallback.</summary>
    public static INPUT[] WinSpace() => [Key(VkLWin, false), Key(VkSpace, false), Key(VkSpace, true), Key(VkLWin, true)];

    public static IEnumerable<INPUT[]> Chunks(INPUT[] events)
    {
        for (var start = 0; start < events.Length;)
        {
            var end = Math.Min(start + ChunkSize, events.Length);
            // A surrogate pair is four events and ChunkSize is not a multiple of four, so a chunk boundary can fall
            // inside one. Windows wants a pair in one call, so step back to where the pair starts.
            while (end > start + 1 && end < events.Length && IsHighSurrogate(events[end - 1]))
            {
                end--;
            }
            yield return events[start..end];
            start = end;
        }
    }

    private static bool IsHighSurrogate(INPUT input) =>
        (input.u.ki.dwFlags & KEYEVENTF_UNICODE) != 0 && char.IsHighSurrogate((char)input.u.ki.wScan);

    private static bool IsExtended(ushort vk) => vk is VkInsert or VkLWin;
}
