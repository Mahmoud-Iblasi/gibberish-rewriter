using System.Globalization;

namespace GibberishRewriter.App.Win;

/// <summary>Either a pair or the notification that explains why there is none.</summary>
internal sealed record PairResolution(LayoutPair? Pair, string? Error);

/// <summary>The <c>layouts</c> setting: "auto" or explicit HKL values, checked against the installed layouts. Pure.</summary>
internal static class LayoutPairResolver
{
    /// <param name="installed">Each installed layout with what its KeyA types plain.</param>
    public static PairResolution Resolve(string latinSetting, string arabicSetting, IReadOnlyList<(uint Hkl, string KeyA)> installed)
    {
        var (latin, latinError) = Pick(latinSetting, installed, char.IsAsciiLetter);
        if (latinError is not null)
        {
            return new PairResolution(null, latinError);
        }
        var (arabic, arabicError) = Pick(arabicSetting, installed, IsArabicLetter);
        if (arabicError is not null)
        {
            return new PairResolution(null, arabicError);
        }
        return latin == arabic
            ? new PairResolution(null, AppMessages.LayoutsSame)
            : new PairResolution(new LayoutPair(latin, arabic), null);
    }

    private static (uint Hkl, string? Error) Pick(
        string setting, IReadOnlyList<(uint Hkl, string KeyA)> installed, Func<char, bool> isScriptLetter)
    {
        if (setting == "auto")
        {
            var matches = installed.Where(layout => layout.KeyA.Length == 1 && isScriptLetter(layout.KeyA[0])).ToList();
            return matches.Count == 1 ? (matches[0].Hkl, null) : (0, AppMessages.LayoutsNotFound);
        }
        var hkl = Hkl.Parse(setting);
        return installed.Any(layout => layout.Hkl == hkl) ? (hkl, null) : (0, AppMessages.LayoutNotInstalled(setting));
    }

    /// <summary>The same test as TextConverter: U+0600–U+06FF with a letter category.</summary>
    private static bool IsArabicLetter(char c) =>
        c is >= '؀' and <= 'ۿ'
        && CharUnicodeInfo.GetUnicodeCategory(c) is UnicodeCategory.UppercaseLetter
            or UnicodeCategory.LowercaseLetter
            or UnicodeCategory.TitlecaseLetter
            or UnicodeCategory.ModifierLetter
            or UnicodeCategory.OtherLetter;
}
