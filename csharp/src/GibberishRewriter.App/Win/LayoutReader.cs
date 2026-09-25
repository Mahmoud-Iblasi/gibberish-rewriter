using GibberishRewriter.Core;
using static GibberishRewriter.App.Win.NativeMethods;

namespace GibberishRewriter.App.Win;

/// <summary>A layout has a dead key, which Gibberish Rewriter doesn't support.</summary>
internal sealed class DeadKeyException(uint layout, string key)
    : Exception($"Layout {Hkl.Format(layout)} has a dead key: {key}.")
{
    public uint Layout { get; } = layout;
}

/// <summary>Installed layouts, and the key table read from Windows.</summary>
internal static class LayoutReader
{
    private const int VkShift = 0x10;
    private const int VkLShift = 0xA0;
    private const int VkCapital = 0x14;
    private const int VkNumLock = 0x90;
    private const int VkKeyA = 0x41;
    private const uint DontChangeKeyboardState = 4;

    /// <summary>Installed layouts as low 32-bit HKL values, in GetKeyboardLayoutList order.</summary>
    public static uint[] InstalledLayouts()
    {
        var handles = new IntPtr[GetKeyboardLayoutList(0, null)];
        var count = GetKeyboardLayoutList(handles.Length, handles);
        return handles.Take(count).Select(Hkl.Low32).ToArray();
    }

    /// <summary>Each installed layout with what its KeyA types plain ("" if KeyA is a dead key), for "auto".</summary>
    public static IReadOnlyList<(uint Hkl, string KeyA)> InstalledWithKeyA() =>
        InstalledLayouts().Select(hkl => (hkl, KeyAText(hkl))).ToList();

    /// <summary>The key table for the pair, keys in keys.json tableKeys order. Throws <see cref="DeadKeyException"/>.</summary>
    public static KeyTable ReadTable(KeyNames names, LayoutPair pair)
    {
        var entries = new List<KeyEntry>(names.TableKeys.Count);
        foreach (var key in names.TableKeys)
        {
            if (!names.TryGetTrigger(key, out var vk))
            {
                throw new InvalidOperationException($"tableKeys lists unknown key {key}.");
            }
            entries.Add(new KeyEntry(key, vk, ReadKey(pair.Latin, key, vk), ReadKey(pair.Arabic, key, vk)));
        }
        return new KeyTable(Hkl.Format(pair.Latin), Hkl.Format(pair.Arabic), entries);
    }

    private static string KeyAText(uint hkl)
    {
        try
        {
            return ReadText(hkl, "KeyA", VkKeyA, KeyState.Plain);
        }
        catch (DeadKeyException)
        {
            return "";
        }
    }

    private static string[] ReadKey(uint hkl, string key, int vk) =>
    [
        ReadText(hkl, key, vk, KeyState.Plain),
        ReadText(hkl, key, vk, KeyState.Shift),
        ReadText(hkl, key, vk, KeyState.Caps),
        ReadText(hkl, key, vk, KeyState.ShiftCaps),
    ];

    private static string ReadText(uint hkl, string key, int vk, KeyState state)
    {
        var handle = Hkl.ToHandle(hkl);
        var keyState = new byte[256];
        keyState[VkNumLock] = 0x01;
        if (state is KeyState.Shift or KeyState.ShiftCaps)
        {
            keyState[VkShift] = 0x80;
            keyState[VkLShift] = 0x80;
        }
        if (state is KeyState.Caps or KeyState.ShiftCaps)
        {
            keyState[VkCapital] = 0x01;
        }
        // Only the low byte: an 0xE0 prefix sets the high bit, which ToUnicodeEx reads as a key release.
        var scan = MapVirtualKeyEx((uint)vk, MAPVK_VK_TO_VSC_EX, handle) & 0xFF;
        var buffer = new char[16];
        var length = ToUnicodeEx((uint)vk, scan, keyState, buffer, buffer.Length, DontChangeKeyboardState, handle);
        return length < 0 ? throw new DeadKeyException(hkl, key) : new string(buffer, 0, length);
    }
}
