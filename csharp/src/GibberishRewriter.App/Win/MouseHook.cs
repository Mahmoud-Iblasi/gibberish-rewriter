using System.Runtime.InteropServices;
using static GibberishRewriter.App.Win.NativeMethods;

namespace GibberishRewriter.App.Win;

/// <summary>Button presses are breaks; every event counts as hook activity.</summary>
internal sealed class MouseHook(Func<EngineSlot?> slot, HookActivity activity, Action<string> log)
    : LowLevelHook(WH_MOUSE_LL, log)
{
    protected override bool OnEvent(IntPtr message, IntPtr data)
    {
        activity.Note(Marshal.PtrToStructure<MSLLHOOKSTRUCT>(data).time);
        if (HookTranslator.IsMouseButtonDown(message))
        {
            slot()?.Engine.OnMouseDown();
        }
        return false;
    }
}
