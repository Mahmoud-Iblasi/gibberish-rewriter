namespace GibberishRewriter.Core;

public enum ChordAction
{
    FixTyped,
    FixSelection,
}

/// <summary>What to do with one key event.</summary>
/// <param name="Swallow">Keep the event from reaching Windows.</param>
/// <param name="Fired">The chord this key-down fired.</param>
/// <param name="ReplayCapsLock">Send one CapsLock press so Caps Lock toggles.</param>
/// <param name="SendMaskKey">Send one press of <see cref="KeyNames.VkMask"/> so Alt or Win don't open menus.</param>
/// <param name="CapsLockToggled">A CapsLock press reaches Windows because of this event.</param>
public readonly record struct ChordDecision(
    bool Swallow,
    ChordAction? Fired = null,
    bool ReplayCapsLock = false,
    bool SendMaskKey = false,
    bool CapsLockToggled = false)
{
    public static ChordDecision Pass => default;

    public static ChordDecision SwallowKey => new(true);
}

/// <summary>Detects chords, swallows their keys and replays CapsLock taps. Engine serializes calls.</summary>
public sealed class ChordDetector
{
    private readonly KeyNames _names;
    private Chord _fixTyped;
    private Chord _fixSelection;
    private bool _chordFiredWhileCapsLockDown;
    private readonly HashSet<int> _swallowedTriggers = [];

    public ChordDetector(KeyNames names, Chord fixTyped, Chord fixSelection)
    {
        _names = names;
        SetChords(fixTyped, fixSelection);
    }

    /// <summary>True while CapsLock is physically held.</summary>
    public bool CapsLockDown { get; private set; }

    private bool CapsLockIsHoldKey => ((_fixTyped.Hold | _fixSelection.Hold) & HoldKeys.CapsLock) != 0;

    /// <summary>Replaces the chords and forgets any half-pressed chord.</summary>
    public void SetChords(Chord fixTyped, Chord fixSelection)
    {
        _fixTyped = fixTyped;
        _fixSelection = fixSelection;
        CapsLockDown = false;
        _chordFiredWhileCapsLockDown = false;
        _swallowedTriggers.Clear();
    }

    /// <summary>Decides one key event this app did not inject.</summary>
    /// <param name="modifiers">Shift, Ctrl, Alt and Win as Windows reports them just before the event.</param>
    public ChordDecision OnKey(int vk, bool down, HoldKeys modifiers)
    {
        if (_swallowedTriggers.Contains(vk))
        {
            if (!down)
            {
                _swallowedTriggers.Remove(vk);
            }
            return ChordDecision.SwallowKey;
        }

        if (vk == KeyNames.VkCapsLock)
        {
            return OnCapsLock(down);
        }

        if (!down || _names.IsModifier(vk))
        {
            return ChordDecision.Pass;
        }

        var held = (modifiers & ~HoldKeys.CapsLock) | (CapsLockDown ? HoldKeys.CapsLock : HoldKeys.None);
        ChordAction action;
        Chord chord;
        if (_fixTyped.TriggerVk == vk && _fixTyped.Hold == held)
        {
            (action, chord) = (ChordAction.FixTyped, _fixTyped);
        }
        else if (_fixSelection.TriggerVk == vk && _fixSelection.Hold == held)
        {
            (action, chord) = (ChordAction.FixSelection, _fixSelection);
        }
        else
        {
            return ChordDecision.Pass;
        }

        _swallowedTriggers.Add(vk);
        if (CapsLockDown)
        {
            _chordFiredWhileCapsLockDown = true;
        }
        return new ChordDecision(true, action, SendMaskKey: (chord.Hold & (HoldKeys.Alt | HoldKeys.Win)) != 0);
    }

    private ChordDecision OnCapsLock(bool down)
    {
        if (!CapsLockIsHoldKey)
        {
            var toggled = down && !CapsLockDown;
            CapsLockDown = down;
            return new ChordDecision(false, CapsLockToggled: toggled);
        }

        if (down)
        {
            if (!CapsLockDown)
            {
                CapsLockDown = true;
                _chordFiredWhileCapsLockDown = false;
            }
            return ChordDecision.SwallowKey;
        }

        var replay = CapsLockDown && !_chordFiredWhileCapsLockDown;
        CapsLockDown = false;
        return new ChordDecision(true, ReplayCapsLock: replay, CapsLockToggled: replay);
    }
}
