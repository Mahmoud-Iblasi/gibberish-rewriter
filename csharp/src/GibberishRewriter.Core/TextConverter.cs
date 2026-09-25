using System.Globalization;
using System.Text;

namespace GibberishRewriter.Core;

/// <summary>A converted selection, and the layout its text belongs to now.</summary>
public sealed record Conversion(string Text, LayoutKind Target);

/// <summary>Converts selected text to the other layout.</summary>
public sealed class TextConverter
{
    private static readonly KeyState[] PlainThenShift = [KeyState.Plain, KeyState.Shift];

    private const int MaxSequencesChecked = 6;

    private readonly WordList _words;

    private readonly KeyTable _table;

    /// <summary>Every character the Latin layout types.</summary>
    private readonly HashSet<char> _latinTypeable = [];

    /// <summary>Every non-empty Arabic text with the Latin text of the same key and state, in table order, plain before shift.</summary>
    private readonly List<(string Arabic, string Latin)> _arabicTexts = [];

    public TextConverter(KeyTable table, WordList words)
    {
        _table = table;
        _words = words;
        foreach (var entry in table.Keys)
        {
            foreach (var text in entry.Latin)
            {
                _latinTypeable.UnionWith(text);
            }
            foreach (var state in PlainThenShift)
            {
                var arabic = entry.TextOn(LayoutKind.Arabic, state);
                if (arabic.Length > 0)
                {
                    _arabicTexts.Add((arabic, entry.TextOn(LayoutKind.Latin, state)));
                }
            }
        }
    }

    /// <summary>Converts <paramref name="text"/>, or returns null when it has no Latin or Arabic letters.</summary>
    public Conversion? Convert(string text)
    {
        var latinLetters = 0;
        var arabicLetters = 0;
        LayoutKind? lastLetter = null;
        foreach (var c in text)
        {
            if (IsLatinLetter(c))
            {
                latinLetters++;
                lastLetter = LayoutKind.Latin;
            }
            else if (IsArabicLetter(c))
            {
                arabicLetters++;
                lastLetter = LayoutKind.Arabic;
            }
        }
        if (lastLetter is not { } last)
        {
            return null;
        }
        var source = arabicLetters > latinLetters ? LayoutKind.Arabic
            : latinLetters > arabicLetters ? LayoutKind.Latin
            : last;
        return source == LayoutKind.Latin
            ? new Conversion(LatinToArabic(text, latinLetters), LayoutKind.Arabic)
            : new Conversion(ArabicToLatin(text), LayoutKind.Latin);
    }

    private static bool IsLatinLetter(char c) => char.IsAsciiLetter(c);

    private static bool IsUpperLatin(char c) => char.IsAsciiLetterUpper(c);

    private static bool IsArabicLetter(char c) =>
        c is >= '\u0600' and <= '\u06FF'
        && CharUnicodeInfo.GetUnicodeCategory(c) is UnicodeCategory.UppercaseLetter
            or UnicodeCategory.LowercaseLetter
            or UnicodeCategory.TitlecaseLetter
            or UnicodeCategory.ModifierLetter
            or UnicodeCategory.OtherLetter;

    /// <summary>Latin text to Arabic: the text was typed on the Latin layout while Arabic was meant.</summary>
    private string LatinToArabic(string text, int latinLetters)
    {
        var allCaps = latinLetters >= 2 && !text.Any(char.IsAsciiLetterLower);
        var result = new StringBuilder(text.Length);
        foreach (var c in text)
        {
            var upper = IsUpperLatin(c);
            var lookup = upper ? char.ToLowerInvariant(c).ToString() : c.ToString();
            if (_table.Find(lookup, LayoutKind.Latin) is not { } key)
            {
                result.Append(c);
                continue;
            }
            var state = !upper ? key.State : allCaps ? KeyState.Caps : KeyState.Shift;
            var arabic = key.Entry.TextOn(LayoutKind.Arabic, state);
            if (arabic.Length > 0)
            {
                result.Append(arabic);
            }
            else
            {
                result.Append(c);
            }
        }
        return result.ToString();
    }

    /// <summary>A converted piece of a word: fixed text, or a two-character sequence one key or two keys could have typed.</summary>
    private readonly record struct Piece(string OneKey, string? TwoKeys);

    /// <summary>Arabic text to Latin: the text was typed on the Arabic layout while Latin was meant.</summary>
    private string ArabicToLatin(string text)
    {
        var result = new StringBuilder(text.Length);
        var wordStart = -1;
        for (var i = 0; i <= text.Length; i++)
        {
            var atBreak = i == text.Length || text[i] is ' ' or '\t' or '\r' or '\n';
            if (!atBreak)
            {
                if (wordStart < 0)
                {
                    wordStart = i;
                }
                continue;
            }
            if (wordStart >= 0)
            {
                result.Append(ConvertWord(text[wordStart..i]));
                wordStart = -1;
            }
            if (i < text.Length)
            {
                result.Append(text[i]);
            }
        }
        return result.ToString();
    }

    private string ConvertWord(string word)
    {
        var pieces = new List<Piece>();
        var i = 0;
        while (i < word.Length)
        {
            if (!_latinTypeable.Contains(word[i]) && LongestArabicMatch(word, i) is { } match)
            {
                var oneKey = match.Latin.Length > 0 ? match.Latin : match.Arabic;
                pieces.Add(new Piece(oneKey, match.Arabic.Length == 2 ? TwoKeys(match.Arabic) : null));
                i += match.Arabic.Length;
            }
            else
            {
                pieces.Add(new Piece(word[i].ToString(), null));
                i++;
            }
        }

        var sequences = pieces.Count(piece => piece.TwoKeys is not null);
        if (sequences is 0 or > MaxSequencesChecked)
        {
            return Build(pieces, 0, sequences);
        }
        for (var combination = 0; combination < 1 << sequences; combination++)
        {
            var candidate = Build(pieces, combination, sequences);
            if (IsEnglishWord(candidate))
            {
                return candidate;
            }
        }
        return Build(pieces, 0, sequences);
    }

    /// <summary>The sequence read as two keys, or null when a character has no key of its own.</summary>
    private string? TwoKeys(string sequence)
    {
        var first = SingleCharacterLatin(sequence[0]);
        var second = SingleCharacterLatin(sequence[1]);
        return first is null || second is null ? null : first + second;
    }

    private string? SingleCharacterLatin(char c)
    {
        foreach (var (arabic, latin) in _arabicTexts)
        {
            if (arabic.Length == 1 && arabic[0] == c && latin.Length > 0)
            {
                return latin;
            }
        }
        return null;
    }

    /// <summary>Bit 1 reads a sequence as two keys. The leftmost sequence is the most significant bit.</summary>
    private static string Build(List<Piece> pieces, int combination, int sequences)
    {
        var text = new StringBuilder();
        var bit = sequences - 1;
        foreach (var piece in pieces)
        {
            if (piece.TwoKeys is null)
            {
                text.Append(piece.OneKey);
                continue;
            }
            text.Append(((combination >> bit) & 1) == 1 ? piece.TwoKeys : piece.OneKey);
            bit--;
        }
        return text.ToString();
    }

    /// <summary>ASCII-lowercases, strips leading and trailing characters other than a–z, and checks the word list.</summary>
    private bool IsEnglishWord(string candidate)
    {
        var lower = string.Create(candidate.Length, candidate, static (span, source) =>
        {
            for (var i = 0; i < source.Length; i++)
            {
                span[i] = char.IsAsciiLetterUpper(source[i]) ? (char)(source[i] + 32) : source[i];
            }
        });
        var start = 0;
        var end = lower.Length;
        while (start < end && !char.IsAsciiLetterLower(lower[start]))
        {
            start++;
        }
        while (end > start && !char.IsAsciiLetterLower(lower[end - 1]))
        {
            end--;
        }
        return end > start && _words.Contains(lower[start..end]);
    }

    /// <summary>The longest Arabic-layout text starting at <paramref name="start"/>; ties go to the earlier one.</summary>
    private (string Arabic, string Latin)? LongestArabicMatch(string text, int start)
    {
        (string Arabic, string Latin)? best = null;
        foreach (var candidate in _arabicTexts)
        {
            if (candidate.Arabic.Length > (best?.Arabic.Length ?? 0)
                && text.AsSpan(start).StartsWith(candidate.Arabic, StringComparison.Ordinal))
            {
                best = candidate;
            }
        }
        return best;
    }
}
