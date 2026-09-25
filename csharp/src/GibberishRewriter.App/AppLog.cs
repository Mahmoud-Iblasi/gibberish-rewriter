using System.Globalization;
using System.Text;

namespace GibberishRewriter.App;

/// <summary>%APPDATA%\GibberishRewriter\logs\csharp.log, rolled over to csharp.log.1 at 1 MB.
/// Callers log event kinds, counts, window class names and errors only, never typed text.</summary>
internal sealed class AppLog(string filePath, long maxBytes = AppLog.DefaultMaxBytes)
{
    public const long DefaultMaxBytes = 1024 * 1024;

    private static readonly UTF8Encoding Utf8NoBom = new(false);

    private readonly object _lock = new();

    public static string DefaultPath => Path.Combine(ConfigFile.AppDataFolder, "logs", "csharp.log");

    public string FilePath { get; } = filePath;

    /// <summary>Any thread. Never throws: a log that can't be written is skipped.</summary>
    public void Write(string message)
    {
        var line = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff", CultureInfo.InvariantCulture) + " " + message + "\n";
        lock (_lock)
        {
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(FilePath)!);
                var file = new FileInfo(FilePath);
                if (file.Exists && file.Length + Utf8NoBom.GetByteCount(line) > maxBytes)
                {
                    File.Move(FilePath, FilePath + ".1", overwrite: true);
                }
                File.AppendAllText(FilePath, line, Utf8NoBom);
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }
    }
}
