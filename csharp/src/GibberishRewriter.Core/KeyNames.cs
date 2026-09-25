using System.Text.Json;

namespace GibberishRewriter.Core;

/// <summary>The keys a chord can hold. Flags, so a chord's hold set is one value.</summary>
[Flags]
public enum HoldKeys
{
    None = 0,
    Shift = 1,
    Ctrl = 2,
    Alt = 4,
    Win = 8,
    CapsLock = 16,
}

/// <summary>Key names and virtual-key codes, loaded from shared/keys.json.</summary>
public sealed class KeyNames
{
    public const int VkBackspace = 0x08;
    public const int VkCapsLock = 0x14;
    public const int VkPacket = 0xE7;

    /// <summary>Unassigned key pressed after an Alt or Win chord fires.</summary>
    public const int VkMask = 0xE8;

    /// <summary>The order hold keys are written in (canonical hotkey text).</summary>
    public static IReadOnlyList<HoldKeys> HoldKeyOrder { get; } =
        [HoldKeys.Shift, HoldKeys.Ctrl, HoldKeys.Alt, HoldKeys.Win, HoldKeys.CapsLock];

    private readonly Dictionary<string, int> _triggers;
    private readonly Dictionary<string, int> _modifiers;
    private readonly Dictionary<HoldKeys, int[]> _holdVks;
    private readonly Dictionary<string, HoldKeys> _holdByName = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<int, HoldKeys> _holdByVk = [];
    private readonly HashSet<int> _modifierVks = [];
    private readonly Dictionary<int, string> _nameByVk = [];

    private KeyNames(
        Dictionary<string, int> triggers,
        Dictionary<string, int> modifiers,
        Dictionary<HoldKeys, int[]> holdVks,
        string[] tableKeys)
    {
        _triggers = triggers;
        TableKeys = tableKeys;
        _modifiers = modifiers;
        _holdVks = holdVks;
        foreach (var (hold, vks) in holdVks)
        {
            _holdByName[hold.ToString()] = hold;
            foreach (var vk in vks)
            {
                _holdByVk[vk] = hold;
                _modifierVks.Add(vk);
            }
        }
        foreach (var (name, vk) in modifiers)
        {
            _modifierVks.Add(vk);
            _nameByVk.TryAdd(vk, name);
        }
        foreach (var (name, vk) in triggers)
        {
            _nameByVk.TryAdd(vk, name);
        }
    }

    /// <summary>The key-table keys in table order, which is also the snapshot's order. LayoutReader reads these.</summary>
    public IReadOnlyList<string> TableKeys { get; }

    public static KeyNames Load(string path) => Parse(File.ReadAllText(path));

    public static KeyNames Parse(string json)
    {
        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;
        var holdVks = new Dictionary<HoldKeys, int[]>();
        foreach (var property in root.GetProperty("holdKeys").EnumerateObject())
        {
            holdVks[Enum.Parse<HoldKeys>(property.Name)] =
                property.Value.EnumerateArray().Select(code => code.GetInt32()).ToArray();
        }
        var triggers = ReadCodes(root.GetProperty("keys"));
        var tableKeys = root.GetProperty("tableKeys").EnumerateArray().Select(name => name.GetString()!).ToArray();
        if (tableKeys.FirstOrDefault(name => !triggers.ContainsKey(name)) is { } unknown)
        {
            throw new FormatException($"tableKeys lists \"{unknown}\", which is not in keys.");
        }
        return new KeyNames(triggers, ReadCodes(root.GetProperty("modifiers")), holdVks, tableKeys);
    }

    private static Dictionary<string, int> ReadCodes(JsonElement element)
    {
        var codes = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        foreach (var property in element.EnumerateObject())
        {
            codes[property.Name] = property.Value.GetInt32();
        }
        return codes;
    }

    /// <summary>Looks up a non-modifier key name, case-insensitively. "`" means Backquote.</summary>
    public bool TryGetTrigger(string name, out int vk) =>
        _triggers.TryGetValue(name == "`" ? "Backquote" : name, out vk);

    /// <summary>Looks up any key name, modifier or not.</summary>
    public bool TryGetVk(string name, out int vk) =>
        TryGetTrigger(name, out vk) || _modifiers.TryGetValue(name, out vk);

    public bool TryGetHoldKey(string name, out HoldKeys hold) => _holdByName.TryGetValue(name, out hold);

    /// <summary>True for hold-key names such as Shift and modifier key names such as ShiftLeft or NumLock.</summary>
    public bool IsModifierName(string name) => _holdByName.ContainsKey(name) || _modifiers.ContainsKey(name);

    public bool IsModifier(int vk) => _modifierVks.Contains(vk);

    public HoldKeys HoldKeyOf(int vk) => _holdByVk.TryGetValue(vk, out var hold) ? hold : HoldKeys.None;

    /// <summary>Codes of every hold key in <paramref name="holds"/>, in canonical order.</summary>
    public IEnumerable<int> VksOf(HoldKeys holds) =>
        HoldKeyOrder.Where(hold => holds.HasFlag(hold)).SelectMany(hold => _holdVks[hold]);

    public string NameOf(int vk) => _nameByVk.TryGetValue(vk, out var name) ? name : $"0x{vk:X2}";
}
