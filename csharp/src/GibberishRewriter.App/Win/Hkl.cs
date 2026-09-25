using System.Globalization;
using GibberishRewriter.Core;

namespace GibberishRewriter.App.Win;

/// <summary>Keyboard layout handles as the config file writes them: the low 32 bits as 8 uppercase hex digits.</summary>
internal static class Hkl
{
    public static uint Low32(IntPtr hkl) => unchecked((uint)hkl.ToInt64());

    public static string Format(uint hkl) => hkl.ToString("X8", CultureInfo.InvariantCulture);

    /// <summary>Parses 8 hex digits, as ConfigParser accepts them.</summary>
    public static uint Parse(string text) => uint.Parse(text, NumberStyles.AllowHexSpecifier, CultureInfo.InvariantCulture);

    /// <summary>The handle Windows uses: sign-extended on 64-bit, as GetKeyboardLayoutList returns it.</summary>
    public static IntPtr ToHandle(uint hkl) => new(unchecked((int)hkl));
}

/// <summary>The resolved layout pair, as low 32-bit HKL values.</summary>
internal sealed record LayoutPair(uint Latin, uint Arabic)
{
    public LayoutKind? KindOf(IntPtr hkl) => KindOf(Hkl.Low32(hkl));

    public LayoutKind? KindOf(uint hkl) =>
        hkl == Latin ? LayoutKind.Latin : hkl == Arabic ? LayoutKind.Arabic : (LayoutKind?)null;

    public uint HklOf(LayoutKind kind) => kind == LayoutKind.Latin ? Latin : Arabic;
}
