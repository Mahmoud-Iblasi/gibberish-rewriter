namespace GibberishRewriter.Core.Tests;

public class WordListTests
{
    [Theory]
    [InlineData("right")]
    [InlineData("about")]
    [InlineData("hello")]
    [InlineData("there")]
    [InlineData("don't")]
    public void Shared_list_has_common_words(string word) =>
        Assert.True(WordList.Load(SharedFiles.PathOf("wordlists/english.txt")).Contains(word));

    [Theory]
    [InlineData("ribt")]
    [InlineData("Right")]
    [InlineData("")]
    public void Shared_list_rejects_non_words_and_capitals(string word) =>
        Assert.False(WordList.Load(SharedFiles.PathOf("wordlists/english.txt")).Contains(word));

    [Fact]
    public void Shared_list_is_lowercase_sorted_unique_and_large()
    {
        var lines = File.ReadAllLines(SharedFiles.PathOf("wordlists/english.txt"));
        Assert.True(lines.Length > 50_000, $"only {lines.Length} words");
        for (var i = 0; i < lines.Length; i++)
        {
            Assert.Equal(lines[i].ToLowerInvariant(), lines[i]);
            if (i > 0)
            {
                Assert.True(string.CompareOrdinal(lines[i - 1], lines[i]) < 0, $"not sorted at line {i + 1}: {lines[i]}");
            }
        }
    }

    [Fact]
    public void Licence_notice_is_saved_next_to_the_list() =>
        Assert.Contains("Kevin Atkinson", SharedFiles.ReadText("wordlists/ESDB-COPYRIGHT.txt"));

    [Fact]
    public void FromWords_trims_and_skips_blank_lines()
    {
        var words = WordList.FromWords(["cat", "  dog ", "", "   "]);
        Assert.Equal(2, words.Count);
        Assert.True(words.Contains("dog"));
    }
}
