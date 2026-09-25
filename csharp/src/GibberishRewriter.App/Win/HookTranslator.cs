using GibberishRewriter.Core;
using static GibberishRewriter.App.Win.NativeMethods;

namespace GibberishRewriter.App.Win;

/// <summary>The pure part of the hooks: hook arguments in Engine's terms.</summary>
internal static class HookTranslator
{
    public const int VkShift = 0x10;
    public const int VkControl = 0x11;
    public const int VkMenu = 0x12;
    public const int VkLWin = 0x5B;
    public const int VkRWin = 0x5C;

    public static bool IsKeyDown(IntPtr message) => (int)message is WM_KEYDOWN or WM_SYSKEYDOWN;

    /// <summary>True for input this app sent: injected, and carrying <see cref="InputBuilder.ExtraInfo"/>.</summary>
    public static bool IsInjectedBySelf(uint flags, UIntPtr extraInfo) =>
        (flags & LLKHF_INJECTED) != 0 && extraInfo == (UIntPtr)InputBuilder.ExtraInfo;

    /// <summary>Shift, Ctrl, Alt and Win from a key-state query such as GetAsyncKeyState.</summary>
    public static HoldKeys Modifiers(Func<int, bool> isDown)
    {
        var modifiers = HoldKeys.None;
        if (isDown(VkShift))
        {
            modifiers |= HoldKeys.Shift;
        }
        if (isDown(VkControl))
        {
            modifiers |= HoldKeys.Ctrl;
        }
        if (isDown(VkMenu))
        {
            modifiers |= HoldKeys.Alt;
        }
        if (isDown(VkLWin) || isDown(VkRWin))
        {
            modifiers |= HoldKeys.Win;
        }
        return modifiers;
    }

    public static bool IsMouseButtonDown(IntPtr message) =>
        (int)message is WM_LBUTTONDOWN or WM_RBUTTONDOWN or WM_MBUTTONDOWN or WM_XBUTTONDOWN;
}
