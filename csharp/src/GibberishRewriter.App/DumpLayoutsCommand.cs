using System.Text;
using GibberishRewriter.App.Win;
using GibberishRewriter.Core;

namespace GibberishRewriter.App;

/// <summary><c>--dump-layouts &lt;file&gt;</c> writes the key table of the configured pair as JSON.</summary>
internal static class DumpLayoutsCommand
{
    /// <param name="configText">The config to take <c>layouts</c> from; null means the defaults.</param>
    /// <returns>The exit code: 0 when the file was written, otherwise 1 with a message on <paramref name="errors"/>.</returns>
    public static int Run(string sharedFolder, string? configText, string outputPath, TextWriter errors)
    {
        var names = KeyNames.Load(Path.Combine(sharedFolder, "keys.json"));
        var parser = new ConfigParser(names, File.ReadAllText(Path.Combine(sharedFolder, "config.default.json")));
        var config = parser.Defaults;
        if (configText is not null)
        {
            var result = parser.Parse(configText);
            if (result.Error is { } error)
            {
                errors.WriteLine(AppMessages.ConfigInvalid(error.Code, error.Message));
                return 1;
            }
            config = result.Config!;
        }

        var resolution = LayoutPairResolver.Resolve(config.LatinLayout, config.ArabicLayout, LayoutReader.InstalledWithKeyA());
        if (resolution.Pair is not { } pair)
        {
            errors.WriteLine(resolution.Error);
            return 1;
        }
        try
        {
            File.WriteAllText(outputPath, LayoutReader.ReadTable(names, pair).ToJson(), new UTF8Encoding(false));
            return 0;
        }
        catch (DeadKeyException exception)
        {
            errors.WriteLine(AppMessages.LayoutHasDeadKeys(Hkl.Format(exception.Layout)));
            return 1;
        }
    }
}
