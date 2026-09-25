using System.Text;

namespace GibberishRewriter.App;

/// <summary>%APPDATA%\GibberishRewriter\config.json, created from the defaults and polled for changes.</summary>
internal sealed class ConfigFile(string filePath)
{
    public const int PollIntervalMs = 2000;

    private static readonly UTF8Encoding Utf8NoBom = new(false);

    private (DateTime WriteTime, long Length)? _stamp;

    public static string AppDataFolder =>
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "GibberishRewriter");

    public static string DefaultPath => Path.Combine(AppDataFolder, "config.json");

    public string FilePath { get; } = filePath;

    /// <summary>Writes the default config if there is no file yet.</summary>
    public void EnsureExists(string defaultText)
    {
        if (File.Exists(FilePath))
        {
            return;
        }
        Directory.CreateDirectory(Path.GetDirectoryName(FilePath)!);
        File.WriteAllText(FilePath, defaultText, Utf8NoBom);
    }

    /// <summary>The file's text on the first call and whenever it changed since, else null. A missing file, or one
    /// another app has locked, reads as unchanged, so the next poll tries again.</summary>
    public string? ReadIfChanged()
    {
        try
        {
            var file = new FileInfo(FilePath);
            if (!file.Exists)
            {
                return null;
            }
            var stamp = (file.LastWriteTimeUtc, file.Length);
            if (stamp == _stamp)
            {
                return null;
            }
            var text = ReadText(FilePath);
            _stamp = stamp;
            return text;
        }
        catch (IOException)
        {
            return null;
        }
        catch (UnauthorizedAccessException)
        {
            return null;
        }
    }

    /// <summary>The file as UTF-8, without a byte order mark at the start.</summary>
    public static string ReadText(string path)
    {
        using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        using var reader = new StreamReader(stream, Utf8NoBom, detectEncodingFromByteOrderMarks: false);
        var text = reader.ReadToEnd();
        return text.StartsWith('﻿') ? text[1..] : text;
    }
}
