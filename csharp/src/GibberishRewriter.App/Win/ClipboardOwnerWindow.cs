namespace GibberishRewriter.App.Win;

/// <summary>A message-only window on the UI thread that owns the app's clipboard writes. The UI thread's message loop
/// answers the messages other apps' clipboard calls send the owner, so it never blocks them.</summary>
internal sealed class ClipboardOwnerWindow : NativeWindow, IDisposable
{
    private static readonly IntPtr MessageOnlyParent = new(-3);

    public ClipboardOwnerWindow() =>
        CreateHandle(new CreateParams { Caption = "GibberishRewriter.ClipboardOwner", Parent = MessageOnlyParent });

    public void Dispose() => DestroyHandle();
}
