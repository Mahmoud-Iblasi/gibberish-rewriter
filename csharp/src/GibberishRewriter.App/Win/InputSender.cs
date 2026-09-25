using System.Runtime.InteropServices;
using static GibberishRewriter.App.Win.NativeMethods;
using Shortcut = GibberishRewriter.Core.Shortcut;

namespace GibberishRewriter.App.Win;

/// <summary>Sends keyboard input with SendInput. Every event carries <see cref="InputBuilder.ExtraInfo"/>.</summary>
internal sealed class InputSender(Action<string> log)
{
    private static readonly int InputSize = Marshal.SizeOf<INPUT>();

    public void KeyPress(int vk) => Send(InputBuilder.KeyPress((ushort)vk));

    public void Backspaces(int count) => Send(InputBuilder.Backspaces(count));

    public void Text(string text) => Send(InputBuilder.Text(text));

    public void Shortcut(Shortcut shortcut, bool console) => Send(InputBuilder.Shortcut(shortcut, console));

    public void WinSpace() => Send(InputBuilder.WinSpace());

    private void Send(INPUT[] events)
    {
        for (var i = 0; i < events.Length; i++)
        {
            // Virtual-key events also get their scan code; some apps read it instead of the virtual key.
            if ((events[i].u.ki.dwFlags & KEYEVENTF_UNICODE) == 0)
            {
                events[i].u.ki.wScan = (ushort)MapVirtualKey(events[i].u.ki.wVk, MAPVK_VK_TO_VSC);
            }
        }
        foreach (var chunk in InputBuilder.Chunks(events))
        {
            var sent = SendInput((uint)chunk.Length, chunk, InputSize);
            if (sent != chunk.Length)
            {
                log($"SendInput sent {sent} of {chunk.Length} events (error {Marshal.GetLastPInvokeError()})");
            }
        }
    }
}
