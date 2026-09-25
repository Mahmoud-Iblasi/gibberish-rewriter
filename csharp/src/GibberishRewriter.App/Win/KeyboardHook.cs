using System.Runtime.InteropServices;
using GibberishRewriter.Core;
using static GibberishRewriter.App.Win.NativeMethods;

namespace GibberishRewriter.App.Win;

/// <summary>Forwards key events to Engine, sends the keys it asks for, swallows when told.</summary>
internal sealed class KeyboardHook(
    Func<EngineSlot?> slot,
    InputSender sender,
    KeyStateTracker keys,
    HookActivity activity,
    Action<string> log) : LowLevelHook(WH_KEYBOARD_LL, log)
{
    protected override bool OnEvent(IntPtr message, IntPtr data)
    {
        var key = Marshal.PtrToStructure<KBDLLHOOKSTRUCT>(data);
        activity.Note(key.time);
        var vk = (int)key.vkCode;
        var down = HookTranslator.IsKeyDown(message);
        var injectedBySelf = HookTranslator.IsInjectedBySelf(key.flags, key.dwExtraInfo);
        if (!injectedBySelf)
        {
            keys.Set(vk, down);
        }
        if (slot() is not { } current)
        {
            return false;
        }

        var window = GetForegroundWindow();
        var layout = GetKeyboardLayout(GetWindowThreadProcessId(window, out _));
        var decision = current.Engine.OnKey(new KeyEvent(
            vk,
            down,
            injectedBySelf,
            vk == KeyNames.VkPacket,
            HookTranslator.Modifiers(IsDownNow),
            window.ToInt64(),
            current.Pair.KindOf(layout)));
        foreach (var send in decision.SendKeys)
        {
            sender.KeyPress(send);
        }
        return decision.Swallow;
    }

    /// <summary>Inside the hook, GetAsyncKeyState still shows the state before the current key.</summary>
    private static bool IsDownNow(int vk) => GetAsyncKeyState(vk) < 0;
}
