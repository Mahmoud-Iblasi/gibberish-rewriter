namespace GibberishRewriter.Core.Tests;

public class TextConverterTests
{
    private static readonly KeyTable Table = KeyTable.Load(SharedFiles.PathOf("layouts/us-arabic101.json"));

    private static TextConverter Converter(params string[] words) => new(Table, WordList.FromWords(words));

    [Theory]
    [InlineData("")]
    [InlineData("123 !")]
    [InlineData("\u064E\u064E")]
    public void Text_without_letters_is_not_converted(string text) =>
        Assert.Null(Converter().Convert(text));

    [Theory]
    [InlineData("lvpfh", "مرحبا")]
    [InlineData("LVPFH", "مرحبا")]
    [InlineData("Lvpfh", "/رحبا")]
    [InlineData("A", "\u0650")]
    [InlineData(";dt phg;?", "كيف حالك؟")]
    [InlineData(",hkj", "وانت")]
    [InlineData("hello\nthere", "اثممخ\nفاثقث")]
    [InlineData("a😀", "ش😀")]
    [InlineData("\u064E\u064Ea", "\u064E\u064Eش")]
    public void Latin_text_is_converted_to_the_Arabic_layout(string text, string expected) =>
        Assert.Equal(new Conversion(expected, LayoutKind.Arabic), Converter().Convert(text));

    [Theory]
    [InlineData("اثممخ", "hello")]
    [InlineData("اثممخ فاثقث اخص شقث غخع", "hello there how are you")]
    [InlineData("Hello اخص شقث غخع", "Hello how are you")]
    [InlineData("كيف حالك؟", ";dt phg;?")]
    [InlineData("ي]", "d]")]
    [InlineData("\u0640\u0640a", "JJa")]
    [InlineData("شلاخعف", "about")]
    public void Arabic_text_is_converted_to_the_Latin_layout(string text, string expected) =>
        Assert.Equal(new Conversion(expected, LayoutKind.Latin), Converter().Convert(text));

    [Theory]
    [InlineData("ab اب", "ab hf", LayoutKind.Latin)]
    [InlineData("اب ab", "اب شلا", LayoutKind.Arabic)]
    public void A_tie_uses_the_script_of_the_last_letter(string text, string expected, LayoutKind target) =>
        Assert.Equal(new Conversion(expected, target), Converter().Convert(text));

    [Theory]
    [InlineData("قهلاف", "right")]
    [InlineData("قهلاف.", "right.")]
    [InlineData("شلاخعف", "about")]
    public void Lam_alef_is_resolved_with_the_word_list(string text, string expected) =>
        Assert.Equal(expected, Converter("right", "about").Convert(text)!.Text);

    [Fact]
    public void Words_not_in_the_list_read_every_sequence_as_one_key() =>
        Assert.Equal("ribt", Converter().Convert("قهلاف")!.Text);

    [Fact]
    public void Combinations_are_tried_in_binary_counting_order_with_the_leftmost_sequence_most_significant() =>
        Assert.Equal("bgh", Converter("ghb", "bgh").Convert("لالا")!.Text);

    [Fact]
    public void Each_word_is_resolved_on_its_own() =>
        Assert.Equal("right b", Converter("right").Convert("قهلاف لا")!.Text);

    [Fact]
    public void Six_sequences_are_still_checked() =>
        Assert.Equal("ghghghghghgh", Converter("ghghghghghgh").Convert("لالالالالالا")!.Text);

    [Fact]
    public void Words_with_more_than_six_sequences_are_not_checked() =>
        Assert.Equal("bbbbbbb", Converter("ghghghghghghgh").Convert("لالالالالالالا")!.Text);

    [Theory]
    [InlineData("لآ", "gN")]
    [InlineData("لأ", "gH")]
    [InlineData("لإ", "gY")]
    public void Every_lam_alef_form_has_a_two_key_reading(string text, string expected) =>
        Assert.Equal(expected, Converter(expected.ToLowerInvariant()).Convert(text)!.Text);
}
