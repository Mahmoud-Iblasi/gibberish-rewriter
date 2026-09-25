using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;

namespace GibberishRewriter.Core;

/// <summary>One side of the layout pair.</summary>
public enum LayoutKind
{
    Latin,
    Arabic,
}

/// <summary>The modifier state of a key press. The value is the index of the text in the snapshot arrays.</summary>
public enum KeyState
{
    Plain = 0,
    Shift = 1,
    Caps = 2,
    ShiftCaps = 3,
}

public static class LayoutKinds
{
    public static LayoutKind Other(this LayoutKind layout) =>
        layout == LayoutKind.Latin ? LayoutKind.Arabic : LayoutKind.Latin;

    public static string ToName(this LayoutKind layout) => layout == LayoutKind.Latin ? "latin" : "arabic";

    public static LayoutKind Parse(string name) => name switch
    {
        "latin" => LayoutKind.Latin,
        "arabic" => LayoutKind.Arabic,
        _ => throw new ArgumentException($"Unknown layout '{name}'.", nameof(name)),
    };

    public static KeyState StateOf(bool shift, bool capsOn) => (KeyState)((shift ? 1 : 0) | (capsOn ? 2 : 0));
}

/// <summary>What one key types on each layout, indexed by <see cref="KeyState"/>. "" means it types nothing.</summary>
public sealed record KeyEntry(string Key, int Vk, IReadOnlyList<string> Latin, IReadOnlyList<string> Arabic)
{
    public string TextOn(LayoutKind layout, KeyState state) =>
        (layout == LayoutKind.Latin ? Latin : Arabic)[(int)state];
}

/// <summary>Text per layout, key and state. Loads and saves the JSON snapshot.</summary>
public sealed class KeyTable
{
    private static readonly KeyState[] PlainThenShift = [KeyState.Plain, KeyState.Shift];
    private static readonly JsonSerializerOptions JsonText = new() { Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping };

    private readonly Dictionary<int, KeyEntry> _byVk;

    public KeyTable(string latinHkl, string arabicHkl, IReadOnlyList<KeyEntry> keys)
    {
        LatinHkl = latinHkl;
        ArabicHkl = arabicHkl;
        Keys = keys;
        _byVk = keys.ToDictionary(entry => entry.Vk);
    }

    public string LatinHkl { get; }
    public string ArabicHkl { get; }

    /// <summary>Keys in table order, the order shared/keys.json lists them in.</summary>
    public IReadOnlyList<KeyEntry> Keys { get; }

    public static KeyTable Load(string path) => Parse(File.ReadAllText(path));

    public static KeyTable Parse(string json)
    {
        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;
        var keys = root.GetProperty("keys").EnumerateArray()
            .Select(key => new KeyEntry(
                key.GetProperty("key").GetString()!,
                key.GetProperty("vk").GetInt32(),
                ReadTexts(key.GetProperty("latin")),
                ReadTexts(key.GetProperty("arabic"))))
            .ToList();
        return new KeyTable(root.GetProperty("latinHkl").GetString()!, root.GetProperty("arabicHkl").GetString()!, keys);
    }

    private static string[] ReadTexts(JsonElement element)
    {
        var texts = element.EnumerateArray().Select(text => text.GetString()!).ToArray();
        return texts.Length == 4
            ? texts
            : throw new FormatException("Each layout needs four texts: plain, shift, caps, shiftCaps.");
    }

    /// <summary>The snapshot format, one key per line.</summary>
    public string ToJson()
    {
        static string Quote(string text) => JsonSerializer.Serialize(text, JsonText);
        static string Texts(IReadOnlyList<string> texts) => "[" + string.Join(", ", texts.Select(Quote)) + "]";

        var json = new StringBuilder();
        json.Append("{\n");
        json.Append($"  \"latinHkl\": {Quote(LatinHkl)},\n");
        json.Append($"  \"arabicHkl\": {Quote(ArabicHkl)},\n");
        json.Append("  \"keys\": [\n");
        for (var i = 0; i < Keys.Count; i++)
        {
            var key = Keys[i];
            var comma = i < Keys.Count - 1 ? "," : "";
            json.Append($"    {{ \"key\": {Quote(key.Key)}, \"vk\": {key.Vk}, \"latin\": {Texts(key.Latin)}, \"arabic\": {Texts(key.Arabic)} }}{comma}\n");
        }
        json.Append("  ]\n}\n");
        return json.ToString();
    }

    public bool Contains(int vk) => _byVk.ContainsKey(vk);

    /// <summary>What the key types on the layout in the state; "" if the key isn't in the table or types nothing.</summary>
    public string TextOf(int vk, LayoutKind layout, KeyState state) =>
        _byVk.TryGetValue(vk, out var entry) ? entry.TextOn(layout, state) : "";

    /// <summary>The first key in table order that types <paramref name="text"/>, trying plain before shift.</summary>
    public (KeyEntry Entry, KeyState State)? Find(string text, LayoutKind layout)
    {
        if (text.Length == 0)
        {
            return null;
        }
        foreach (var entry in Keys)
        {
            foreach (var state in PlainThenShift)
            {
                if (entry.TextOn(layout, state) == text)
                {
                    return (entry, state);
                }
            }
        }
        return null;
    }
}
