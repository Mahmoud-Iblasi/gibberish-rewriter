namespace GibberishRewriter.Core;

/// <summary>One recorded key press: what it typed, and what the same key and state type on the other layout.</summary>
public sealed record KeyRecord(int Vk, bool Shift, bool CapsOn, string Text, string OtherText);

/// <summary>The keys typed since the last break. Engine serializes access.</summary>
public sealed class TypingRun
{
    private readonly List<KeyRecord> _records = [];
    private int _maxLength;

    public TypingRun(int maxLength) => _maxLength = maxLength;

    /// <summary>The most records kept. Lowering it drops the oldest records.</summary>
    public int MaxLength
    {
        get => _maxLength;
        set
        {
            _maxLength = value;
            DropOldest();
        }
    }

    public long Window { get; private set; }

    public LayoutKind Layout { get; private set; }

    public bool IsEmpty => _records.Count == 0;

    /// <summary>True after a fix: the run is kept only for undo.</summary>
    public bool Sealed { get; private set; }

    public IReadOnlyList<KeyRecord> Records => _records;

    public string Text => string.Concat(_records.Select(record => record.Text));

    public string OtherText => string.Concat(_records.Select(record => record.OtherText));

    public void Clear()
    {
        _records.Clear();
        Sealed = false;
    }

    /// <summary>Adds a record, first clearing the run if it is sealed or belongs to another window or layout.</summary>
    public void Record(long window, LayoutKind layout, KeyRecord record)
    {
        if (!IsEmpty && (Sealed || window != Window || layout != Layout))
        {
            Clear();
        }
        if (IsEmpty)
        {
            Window = window;
            Layout = layout;
        }
        _records.Add(record);
        DropOldest();
    }

    /// <summary>Removes the last character of the run's text, as the app did.</summary>
    public void Backspace(KeyTable table)
    {
        if (IsEmpty)
        {
            return;
        }
        if (Sealed)
        {
            Clear();
            return;
        }

        var last = _records[^1];
        _records.RemoveAt(_records.Count - 1);
        if (last.Text.Length <= 1)
        {
            return;
        }

        var remaining = last.Text[..^1];
        if (table.Find(remaining, Layout) is not { } found)
        {
            Clear();
            return;
        }
        var other = found.Entry.TextOn(Layout.Other(), found.State);
        _records.Add(new KeyRecord(
            found.Entry.Vk,
            found.State == KeyState.Shift,
            false,
            remaining,
            other.Length > 0 ? other : remaining));
    }

    /// <summary>After a fix: the run now describes the fixed text, on the other layout, kept only for undo.</summary>
    public void SwapAfterFix()
    {
        if (IsEmpty)
        {
            return;
        }
        for (var i = 0; i < _records.Count; i++)
        {
            var record = _records[i];
            _records[i] = record with { Text = record.OtherText, OtherText = record.Text };
        }
        Layout = Layout.Other();
        Sealed = true;
    }

    private void DropOldest()
    {
        if (_records.Count > _maxLength)
        {
            _records.RemoveRange(0, _records.Count - _maxLength);
        }
    }
}
