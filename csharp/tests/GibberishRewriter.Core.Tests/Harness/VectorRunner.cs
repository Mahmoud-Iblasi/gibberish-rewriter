using System.Text.Json;

namespace GibberishRewriter.Core.Tests.Harness;

/// <summary>Loads a vector file and finds vectors by name. Names are unique within a file.</summary>
internal static class VectorFile
{
    public static IEnumerable<object[]> Names(string relative) =>
        Load(relative).Keys.Select(name => new object[] { name });

    public static JsonElement Get(string relative, string name) => Load(relative)[name];

    private static Dictionary<string, JsonElement> Load(string relative)
    {
        using var document = JsonDocument.Parse(SharedFiles.ReadText(relative));
        return document.RootElement.EnumerateArray()
            .ToDictionary(vector => vector.GetProperty("name").GetString()!, vector => vector.Clone());
    }
}

/// <summary>Feeds one vector's events to a real Engine with a FakePlatform (plan Task 10, vector harness rules).</summary>
internal sealed class VectorRunner
{
    public static readonly KeyNames Names = KeyNames.Load(SharedFiles.PathOf("keys.json"));
    public static readonly KeyTable Table = KeyTable.Load(SharedFiles.PathOf("layouts/us-arabic101.json"));

    private static readonly TextConverter Converter =
        new(Table, WordList.Load(SharedFiles.PathOf("wordlists/english.txt")));

    private static readonly ConfigParser Parser = new(Names, SharedFiles.ReadText("config.default.json"));

    private readonly HashSet<int> _down = [];
    private readonly Queue<ChordAction> _started = new();

    public VectorRunner(JsonElement vector)
    {
        var configText = vector.TryGetProperty("config", out var config) ? config.GetRawText() : "{}";
        Config = Parser.Parse(configText).Config
            ?? throw new InvalidOperationException($"Invalid config in vector: {configText}");

        Platform = new FakePlatform
        {
            Layout = vector.TryGetProperty("layout", out var layout) ? ParseLayout(layout.GetString()!) : LayoutKind.Latin,
            IsConsole = Flag(vector, "console"),
            IsBlockedByElevation = Flag(vector, "blockedByElevation"),
            ReleaseInTime = !Flag(vector, "releaseTimeout"),
            ClipboardText = vector.TryGetProperty("clipboard", out var clipboard) ? clipboard.GetString() : null,
            Selection = vector.TryGetProperty("selection", out var selection) ? selection.GetString() : null,
            ClipboardLocked = vector.TryGetProperty("clipboardLocked", out var locked) ? locked.GetString() : null,
        };

        Engine = new Engine(Names, Table, Converter, Config, Platform, _started.Enqueue, Flag(vector, "capsLock"));
    }

    public AppConfig Config { get; private set; }
    public FakePlatform Platform { get; }
    public Engine Engine { get; }

    /// <summary>One decision string per key event.</summary>
    public List<string> Decisions { get; } = [];

    /// <summary>Expected platform calls of a vector, as strings comparable with <see cref="FakePlatform.Calls"/>.</summary>
    public static List<string> ExpectedCalls(JsonElement vector) =>
        vector.GetProperty("expect").EnumerateArray()
            .Select(call => call.EnumerateObject().Single())
            .Select(field => field.Value.ValueKind == JsonValueKind.Number
                ? $"{field.Name} {field.Value.GetInt32()}"
                : $"{field.Name} {field.Value.GetString()}")
            .ToList();

    public void Run(JsonElement events)
    {
        foreach (var e in events.EnumerateArray())
        {
            Feed(e);
        }
    }

    private static bool Flag(JsonElement vector, string name) =>
        vector.TryGetProperty(name, out var value) && value.GetBoolean();

    private static LayoutKind? ParseLayout(string name) => name == "other" ? null : LayoutKinds.Parse(name);

    private static string HoldKeyName(HoldKeys hold) => hold switch
    {
        HoldKeys.Shift => "ShiftLeft",
        HoldKeys.Ctrl => "ControlLeft",
        HoldKeys.Alt => "AltLeft",
        HoldKeys.Win => "MetaLeft",
        _ => "CapsLock",
    };

    private void Feed(JsonElement e)
    {
        if (e.TryGetProperty("tap", out var tap))
        {
            var shift = Flag(e, "shift");
            if (shift)
            {
                Key("ShiftLeft", true);
            }
            Key(tap.GetString()!, true);
            Key(tap.GetString()!, false);
            if (shift)
            {
                Key("ShiftLeft", false);
            }
        }
        else if (e.TryGetProperty("down", out var down))
        {
            Key(down.GetString()!, true);
        }
        else if (e.TryGetProperty("up", out var up))
        {
            Key(up.GetString()!, false);
        }
        else if (e.TryGetProperty("chord", out var chordName))
        {
            PressChord(chordName.GetString()!, e.TryGetProperty("during", out var during) ? during.Clone() : null);
        }
        else if (e.TryGetProperty("mouseDown", out _))
        {
            Engine.OnMouseDown();
        }
        else if (e.TryGetProperty("window", out var window))
        {
            Platform.Window = window.GetInt64();
        }
        else if (e.TryGetProperty("layout", out var layout))
        {
            Platform.Layout = ParseLayout(layout.GetString()!);
        }
        else if (e.TryGetProperty("packet", out var packet))
        {
            foreach (var _ in packet.GetString()!)
            {
                Send(KeyNames.VkPacket, true, isPacket: true);
                Send(KeyNames.VkPacket, false, isPacket: true);
            }
        }
        else if (e.TryGetProperty("enabled", out var enabled))
        {
            Engine.Enabled = enabled.GetBoolean();
        }
        else if (e.TryGetProperty("capsLock", out var capsLock))
        {
            Engine.SetCapsLockOn(capsLock.GetBoolean());
        }
        else if (e.TryGetProperty("elevated", out var elevated))
        {
            Platform.IsBlockedByElevation = elevated.GetBoolean();
        }
        else if (e.TryGetProperty("missedInput", out var missed))
        {
            Engine.ResetAfterMissedInput(missed.GetProperty("capsLock").GetBoolean());
        }
        else if (e.TryGetProperty("config", out var reload))
        {
            Config = Parser.Parse(reload.GetRawText()).Config
                ?? throw new InvalidOperationException($"Invalid config event: {reload.GetRawText()}");
            Engine.ApplyConfig(Config);
        }
        else
        {
            throw new InvalidOperationException($"Unknown vector event: {e.GetRawText()}");
        }
    }

    private void PressChord(string name, JsonElement? during)
    {
        var chord = name switch
        {
            "fixTyped" => Config.FixTyped,
            "fixSelection" => Config.FixSelection,
            _ => throw new InvalidOperationException($"Unknown chord '{name}'."),
        };
        var holds = KeyNames.HoldKeyOrder.Where(hold => chord.Hold.HasFlag(hold)).Select(HoldKeyName).ToList();
        var trigger = Names.NameOf(chord.TriggerVk);

        foreach (var hold in holds)
        {
            Key(hold, true);
        }
        if (during is { } duringEvents)
        {
            Platform.DuringAction = () => Run(duringEvents);
        }
        Key(trigger, true);
        Platform.DuringAction = null;
        Key(trigger, false);
        for (var i = holds.Count - 1; i >= 0; i--)
        {
            Key(holds[i], false);
        }
    }

    private void Key(string name, bool down)
    {
        if (!Names.TryGetVk(name, out var vk))
        {
            throw new InvalidOperationException($"Unknown key name '{name}' in vector.");
        }
        Send(vk, down, isPacket: false);
    }

    private void Send(int vk, bool down, bool isPacket)
    {
        var modifiers = HoldKeys.None;
        foreach (var held in _down)
        {
            modifiers |= Names.HoldKeyOf(held);
        }
        modifiers &= ~HoldKeys.CapsLock;

        var decision = Engine.OnKey(new KeyEvent(vk, down, false, isPacket, modifiers, Platform.Window, Platform.Layout));
        if (down)
        {
            _down.Add(vk);
        }
        else
        {
            _down.Remove(vk);
        }

        var started = new List<ChordAction>();
        while (_started.TryDequeue(out var action))
        {
            started.Add(action);
        }

        var text = decision.Swallow ? "swallow" : "pass";
        foreach (var action in started)
        {
            text += action == ChordAction.FixTyped ? " fire:fixTyped" : " fire:fixSelection";
        }
        foreach (var sent in decision.SendKeys)
        {
            text += " send:" + Names.NameOf(sent);
        }
        Decisions.Add(text);

        foreach (var action in started)
        {
            Engine.RunAction(action);
        }
    }
}
