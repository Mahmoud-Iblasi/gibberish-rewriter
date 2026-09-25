using System.Runtime.InteropServices;
using System.Text;
using GibberishRewriter.Core;
using static GibberishRewriter.App.Win.NativeMethods;

namespace GibberishRewriter.App.Win;

/// <summary>Saves, reads, writes and restores the clipboard. Called on the action thread; the owner window lives on the UI thread.</summary>
internal sealed class ClipboardService
{
    public const int OpenAttempts = 10;
    public const int OpenRetryMs = 20;

    /// <summary>CF_BITMAP, CF_METAFILEPICT, CF_PALETTE, CF_ENHMETAFILE, CF_OWNERDISPLAY, CF_DSPBITMAP,
    /// CF_DSPMETAFILEPICT, CF_DSPENHMETAFILE: their data is a GDI handle, not memory.</summary>
    private static readonly uint[] GdiFormats = [2, 3, 9, 14, 0x80, 0x82, 0x83, 0x8E];

    private readonly Func<IntPtr> _owner;
    private readonly Action<string> _log;
    private readonly Action<int> _sleep;
    private readonly uint[] _exclusionFormats;

    public ClipboardService(Func<IntPtr> owner, Action<string> log, Action<int> sleep)
    {
        _owner = owner;
        _log = log;
        _sleep = sleep;
        _exclusionFormats =
        [
            RegisterClipboardFormat("ExcludeClipboardContentFromMonitorProcessing"),
            RegisterClipboardFormat("CanIncludeInClipboardHistory"),
            RegisterClipboardFormat("CanUploadToCloudClipboard"),
        ];
    }

    /// <summary>False for GDI formats and CF_PRIVATEFIRST–CF_GDIOBJLAST, whose data can't be copied as memory.</summary>
    public static bool IsMemoryFormat(uint format) => !GdiFormats.Contains(format) && format is not (>= 0x200 and <= 0x3FF);

    public uint Sequence() => GetClipboardSequenceNumber();

    public object Save()
    {
        var formats = new List<(uint Format, byte[] Bytes)>();
        using (Open())
        {
            for (var format = EnumClipboardFormats(0); format != 0; format = EnumClipboardFormats(format))
            {
                if (!IsMemoryFormat(format))
                {
                    _log($"Clipboard format {format} is not saved (GDI or private data)");
                    continue;
                }
                if (ReadBytes(format) is { } bytes)
                {
                    formats.Add((format, bytes));
                }
            }
        }
        return new SavedClipboard(formats);
    }

    public void Restore(object saved)
    {
        var formats = ((SavedClipboard)saved).Formats;
        using (Open())
        {
            EmptyClipboard();
            if (formats.Count == 0)
            {
                return;
            }
            foreach (var (format, bytes) in formats)
            {
                WriteBytes(format, bytes);
            }
            WriteExclusionMarkers();
        }
    }

    public string? ReadText()
    {
        using (Open())
        {
            if (ReadBytes(CF_UNICODETEXT) is not { } bytes)
            {
                return null;
            }
            var text = Encoding.Unicode.GetString(bytes);
            var end = text.IndexOf('\0');
            return end >= 0 ? text[..end] : text;
        }
    }

    public void SetText(string text)
    {
        using (Open())
        {
            EmptyClipboard();
            if (!WriteBytes(CF_UNICODETEXT, Encoding.Unicode.GetBytes(text + "\0")))
            {
                throw new ClipboardUnavailableException("SetClipboardData failed for the converted text.");
            }
            WriteExclusionMarkers();
        }
    }

    private Lease Open()
    {
        for (var attempt = 1; ; attempt++)
        {
            if (OpenClipboard(_owner()))
            {
                return new Lease();
            }
            if (attempt == OpenAttempts)
            {
                throw new ClipboardUnavailableException(
                    $"OpenClipboard failed {OpenAttempts} times (error {Marshal.GetLastPInvokeError()}).");
            }
            _sleep(OpenRetryMs);
        }
    }

    private static byte[]? ReadBytes(uint format)
    {
        var handle = GetClipboardData(format);
        if (handle == IntPtr.Zero)
        {
            return null;
        }
        var size = (ulong)GlobalSize(handle);
        if (size > int.MaxValue)
        {
            return null;
        }
        var pointer = GlobalLock(handle);
        if (pointer == IntPtr.Zero)
        {
            return null;
        }
        try
        {
            var bytes = new byte[size];
            Marshal.Copy(pointer, bytes, 0, bytes.Length);
            return bytes;
        }
        finally
        {
            GlobalUnlock(handle);
        }
    }

    /// <summary>Copies the bytes into a new global block and hands it to the clipboard. False if that failed.</summary>
    private bool WriteBytes(uint format, byte[] bytes)
    {
        var handle = GlobalAlloc(GMEM_MOVEABLE, (UIntPtr)(uint)Math.Max(bytes.Length, 1));
        var pointer = handle == IntPtr.Zero ? IntPtr.Zero : GlobalLock(handle);
        if (pointer == IntPtr.Zero)
        {
            if (handle != IntPtr.Zero)
            {
                GlobalFree(handle);
            }
            _log($"Couldn't allocate {bytes.Length} bytes for clipboard format {format}");
            return false;
        }
        Marshal.Copy(bytes, 0, pointer, bytes.Length);
        GlobalUnlock(handle);
        if (SetClipboardData(format, handle) == IntPtr.Zero)
        {
            GlobalFree(handle);
            _log($"SetClipboardData failed for format {format} (error {Marshal.GetLastPInvokeError()})");
            return false;
        }
        return true;
    }

    /// <summary>Keeps this app's writes out of clipboard history and cloud sync.</summary>
    private void WriteExclusionMarkers()
    {
        foreach (var format in _exclusionFormats)
        {
            WriteBytes(format, BitConverter.GetBytes(0));
        }
    }

    private sealed record SavedClipboard(List<(uint Format, byte[] Bytes)> Formats);

    private readonly struct Lease : IDisposable
    {
        public void Dispose() => CloseClipboard();
    }
}
