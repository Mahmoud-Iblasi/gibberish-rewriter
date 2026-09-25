namespace GibberishRewriter.Core;

/// <summary>Lowercase English words from shared/wordlists/english.txt.</summary>
public sealed class WordList
{
    private readonly HashSet<string> _words;

    private WordList(HashSet<string> words) => _words = words;

    public static WordList Load(string path) => FromWords(File.ReadLines(path));

    public static WordList FromWords(IEnumerable<string> words) =>
        new(new HashSet<string>(
            words.Select(word => word.Trim()).Where(word => word.Length > 0),
            StringComparer.Ordinal));

    public int Count => _words.Count;

    /// <summary>Exact, case-sensitive lookup. The list holds lowercase words, so lowercase first.</summary>
    public bool Contains(string word) => _words.Contains(word);
}
