using System.Globalization;
using System.Text.Json;

namespace GibberishRewriter.Core;

/// <summary>A set of hold keys plus one trigger key.</summary>
public readonly record struct Chord(HoldKeys Hold, int TriggerVk)
{
    /// <summary>Canonical hotkey text: hold keys in the order Shift, Ctrl, Alt, Win, CapsLock, then the trigger.</summary>
    public string Format(KeyNames names)
    {
        var hold = Hold;
        return string.Join("+", KeyNames.HoldKeyOrder
            .Where(h => hold.HasFlag(h))
            .Select(h => h.ToString())
            .Append(names.NameOf(TriggerVk)));
    }
}

/// <summary>A valid config. Layouts are "auto" or 8 uppercase hex digits.</summary>
public sealed record AppConfig(
    bool Enabled,
    Chord FixTyped,
    Chord FixSelection,
    bool SwitchLayoutAfterFix,
    string LatinLayout,
    string ArabicLayout,
    int MaxRunLength,
    int ClipboardTimeoutMs,
    int PasteRestoreDelayMs,
    int ReleaseTimeoutMs);

public sealed record ConfigError(string Code, string Message);

/// <summary>Exactly one of <see cref="Config"/> and <see cref="Error"/> is set.</summary>
public sealed record ConfigResult(AppConfig? Config, ConfigError? Error);

/// <summary>Parses config text over the defaults from shared/config.default.json.</summary>
public sealed class ConfigParser
{
    private readonly KeyNames _names;

    public ConfigParser(KeyNames names, string defaultJson)
    {
        _names = names;
        var builder = new Builder();
        var error = Apply(defaultJson, builder);
        if (error is not null)
        {
            throw new FormatException($"The default config is invalid: {error.Code}: {error.Message}");
        }
        Defaults = builder.Build() ?? throw new FormatException("The default config must set every field.");
    }

    public AppConfig Defaults { get; }

    public ConfigResult Parse(string json)
    {
        var builder = new Builder(Defaults);
        var error = Apply(json, builder);
        return error is null ? new ConfigResult(builder.Build()!, null) : new ConfigResult(null, error);
    }

    /// <summary>Parses a hotkey string such as "Shift+CapsLock+Tab".</summary>
    public (Chord Chord, ConfigError? Error) ParseChord(string text, string path)
    {
        var parts = text.Split('+').Select(part => part.Trim()).ToArray();
        var hold = HoldKeys.None;
        foreach (var part in parts[..^1])
        {
            if (_names.TryGetHoldKey(part, out var key))
            {
                hold |= key;
            }
            else if (_names.IsModifierName(part) || _names.TryGetTrigger(part, out _))
            {
                return (default, new ConfigError("hotkey.notHoldKey",
                    $"{path}: \"{part}\" can't be held. Hold keys are Shift, Ctrl, Alt, Win and CapsLock."));
            }
            else
            {
                return (default, new ConfigError("hotkey.unknownKey", $"{path}: unknown key \"{part}\"."));
            }
        }

        var trigger = parts[^1];
        if (_names.IsModifierName(trigger))
        {
            return (default, new ConfigError("hotkey.triggerIsModifier",
                $"{path}: the last key, \"{trigger}\", must not be a modifier."));
        }
        if (!_names.TryGetTrigger(trigger, out var vk))
        {
            return (default, new ConfigError("hotkey.unknownKey", $"{path}: unknown key \"{trigger}\"."));
        }
        if (hold == HoldKeys.None)
        {
            return (default, new ConfigError("hotkey.noHoldKey",
                $"{path}: add at least one hold key (Shift, Ctrl, Alt, Win or CapsLock)."));
        }
        return (new Chord(hold, vk), null);
    }

    private ConfigError? Apply(string json, Builder config)
    {
        JsonDocument document;
        try
        {
            document = JsonDocument.Parse(json);
        }
        catch (JsonException exception)
        {
            return new ConfigError("json.invalid", $"The config is not valid JSON: {exception.Message}");
        }

        using (document)
        {
            if (document.RootElement.ValueKind != JsonValueKind.Object)
            {
                return new ConfigError("json.invalid", "The config must be a JSON object.");
            }
            if (FindRepeatedField(document.RootElement, "") is { } repeated)
            {
                return new ConfigError("json.invalid", $"{repeated} appears more than once.");
            }
            if (ApplyRoot(document.RootElement, config) is { } error)
            {
                return error;
            }
        }

        return config.FixTyped is { } fixTyped && config.FixSelection is { } fixSelection && fixTyped == fixSelection
            ? new ConfigError("hotkey.duplicate", "hotkeys.fixTyped and hotkeys.fixSelection are the same chord.")
            : null;
    }

    private ConfigError? ApplyRoot(JsonElement root, Builder config) =>
        ForEachField(root, "", field => field.Name switch
        {
            "enabled" => ReadBool(field, "enabled", value => config.Enabled = value),
            "hotkeys" => ReadObject(field, "hotkeys", hotkeys => ForEachField(hotkeys, "hotkeys.", hotkey => hotkey.Name switch
            {
                "fixTyped" => ReadChord(hotkey, "hotkeys.fixTyped", chord => config.FixTyped = chord),
                "fixSelection" => ReadChord(hotkey, "hotkeys.fixSelection", chord => config.FixSelection = chord),
                _ => UnknownField("hotkeys." + hotkey.Name),
            })),
            "switchLayoutAfterFix" => ReadBool(field, "switchLayoutAfterFix", value => config.SwitchLayoutAfterFix = value),
            "layouts" => ReadObject(field, "layouts", layouts => ForEachField(layouts, "layouts.", layout => layout.Name switch
            {
                "latin" => ReadLayout(layout, "layouts.latin", value => config.LatinLayout = value),
                "arabic" => ReadLayout(layout, "layouts.arabic", value => config.ArabicLayout = value),
                _ => UnknownField("layouts." + layout.Name),
            })),
            "maxRunLength" => ReadInt(field, "maxRunLength", 10, 10000, value => config.MaxRunLength = value),
            "clipboardTimeoutMs" => ReadInt(field, "clipboardTimeoutMs", 50, 10000, value => config.ClipboardTimeoutMs = value),
            "pasteRestoreDelayMs" => ReadInt(field, "pasteRestoreDelayMs", 50, 10000, value => config.PasteRestoreDelayMs = value),
            "releaseTimeoutMs" => ReadInt(field, "releaseTimeoutMs", 50, 10000, value => config.ReleaseTimeoutMs = value),
            _ => UnknownField(field.Name),
        });

    /// <summary>The path of the first field name repeated within one object, anywhere in the document.</summary>
    private static string? FindRepeatedField(JsonElement element, string prefix)
    {
        if (element.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in element.EnumerateArray())
            {
                if (FindRepeatedField(item, prefix) is { } inItem)
                {
                    return inItem;
                }
            }
            return null;
        }
        if (element.ValueKind != JsonValueKind.Object)
        {
            return null;
        }
        var seen = new HashSet<string>(StringComparer.Ordinal);
        foreach (var field in element.EnumerateObject())
        {
            if (!seen.Add(field.Name))
            {
                return prefix + field.Name;
            }
            if (FindRepeatedField(field.Value, prefix + field.Name + ".") is { } inField)
            {
                return inField;
            }
        }
        return null;
    }

    private static ConfigError? ForEachField(JsonElement element, string prefix, Func<JsonProperty, ConfigError?> apply)
    {
        foreach (var field in element.EnumerateObject())
        {
            if (apply(field) is { } error)
            {
                return error;
            }
        }
        return null;
    }

    private static ConfigError UnknownField(string path) =>
        new("field.unknown", $"Unknown setting \"{path}\".");

    private static ConfigError TypeError(string path, string expected) =>
        new("field.type", $"{path} must be {expected}.");

    private static ConfigError? ReadObject(JsonProperty field, string path, Func<JsonElement, ConfigError?> apply) =>
        field.Value.ValueKind == JsonValueKind.Object ? apply(field.Value) : TypeError(path, "an object");

    private static ConfigError? ReadBool(JsonProperty field, string path, Action<bool> set)
    {
        if (field.Value.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
        {
            return TypeError(path, "true or false");
        }
        set(field.Value.GetBoolean());
        return null;
    }

    private static ConfigError? ReadInt(JsonProperty field, string path, int min, int max, Action<int> set)
    {
        var raw = field.Value.ValueKind == JsonValueKind.Number ? field.Value.GetRawText() : "";
        var digits = raw.StartsWith('-') ? raw[1..] : raw;
        if (digits.Length == 0 || !digits.All(char.IsAsciiDigit))
        {
            return TypeError(path, "a whole number");
        }
        if (!long.TryParse(raw, NumberStyles.AllowLeadingSign, CultureInfo.InvariantCulture, out var number)
            || number < min || number > max)
        {
            return new ConfigError("number.range", $"{path} must be from {min} to {max}.");
        }
        set((int)number);
        return null;
    }

    private static ConfigError? ReadLayout(JsonProperty field, string path, Action<string> set)
    {
        if (field.Value.ValueKind != JsonValueKind.String)
        {
            return TypeError(path, "a string");
        }
        var text = field.Value.GetString()!;
        if (text.Equals("auto", StringComparison.OrdinalIgnoreCase))
        {
            set("auto");
            return null;
        }
        if (text.Length == 8 && text.All(char.IsAsciiHexDigit))
        {
            set(text.ToUpperInvariant());
            return null;
        }
        return new ConfigError("layout.invalid",
            $"{path} must be \"auto\" or 8 hex digits such as \"04090409\", not \"{text}\".");
    }

    private ConfigError? ReadChord(JsonProperty field, string path, Action<Chord> set)
    {
        if (field.Value.ValueKind != JsonValueKind.String)
        {
            return TypeError(path, "a string");
        }
        var (chord, error) = ParseChord(field.Value.GetString()!, path);
        if (error is null)
        {
            set(chord);
        }
        return error;
    }

    /// <summary>A config under construction. Every field is null until set.</summary>
    private sealed class Builder
    {
        public Builder()
        {
        }

        public Builder(AppConfig start)
        {
            Enabled = start.Enabled;
            FixTyped = start.FixTyped;
            FixSelection = start.FixSelection;
            SwitchLayoutAfterFix = start.SwitchLayoutAfterFix;
            LatinLayout = start.LatinLayout;
            ArabicLayout = start.ArabicLayout;
            MaxRunLength = start.MaxRunLength;
            ClipboardTimeoutMs = start.ClipboardTimeoutMs;
            PasteRestoreDelayMs = start.PasteRestoreDelayMs;
            ReleaseTimeoutMs = start.ReleaseTimeoutMs;
        }

        public bool? Enabled { get; set; }
        public Chord? FixTyped { get; set; }
        public Chord? FixSelection { get; set; }
        public bool? SwitchLayoutAfterFix { get; set; }
        public string? LatinLayout { get; set; }
        public string? ArabicLayout { get; set; }
        public int? MaxRunLength { get; set; }
        public int? ClipboardTimeoutMs { get; set; }
        public int? PasteRestoreDelayMs { get; set; }
        public int? ReleaseTimeoutMs { get; set; }

        public AppConfig? Build() =>
            Enabled is { } enabled
            && FixTyped is { } fixTyped
            && FixSelection is { } fixSelection
            && SwitchLayoutAfterFix is { } switchLayout
            && LatinLayout is { } latin
            && ArabicLayout is { } arabic
            && MaxRunLength is { } maxRunLength
            && ClipboardTimeoutMs is { } clipboardTimeout
            && PasteRestoreDelayMs is { } pasteRestoreDelay
            && ReleaseTimeoutMs is { } releaseTimeout
                ? new AppConfig(enabled, fixTyped, fixSelection, switchLayout, latin, arabic,
                    maxRunLength, clipboardTimeout, pasteRestoreDelay, releaseTimeout)
                : null;
    }
}
