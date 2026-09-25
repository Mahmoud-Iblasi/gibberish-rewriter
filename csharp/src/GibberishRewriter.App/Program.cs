using GibberishRewriter.App.Win;

namespace GibberishRewriter.App;

internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        var shared = Path.Combine(AppContext.BaseDirectory, "shared");
        if (args is ["--dump-layouts", var output])
        {
            var configText = File.Exists(ConfigFile.DefaultPath) ? ConfigFile.ReadText(ConfigFile.DefaultPath) : null;
            try
            {
                return DumpLayoutsCommand.Run(shared, configText, output, Console.Error);
            }
            catch (Exception exception) when (Startup.IsSharedFileProblem(exception))
            {
                Console.Error.WriteLine(AppMessages.SharedFilesUnreadable(shared, exception.Message));
                return 2;
            }
        }

        ApplicationConfiguration.Initialize();
        using var instance = SingleInstance.TryAcquire();
        if (instance is null)
        {
            MessageBox.Show(AppMessages.AlreadyRunning, AppMessages.Title, MessageBoxButtons.OK, MessageBoxIcon.Information);
            return 1;
        }

        var log = new AppLog(AppLog.DefaultPath);
        Application.ThreadException += (_, e) => log.Write($"UI error: {e.Exception.GetType().Name}");
        AppDomain.CurrentDomain.UnhandledException += (_, e) => log.Write($"Crash: {e.ExceptionObject.GetType().Name}");

        AppHost host;
        try
        {
            host = new AppHost(shared, log);
        }
        catch (Exception exception) when (Startup.IsSharedFileProblem(exception))
        {
            // Without shared/ there is no tray icon to notify from, so this is the one message box.
            log.Write($"Can't read the shared files: {exception.GetType().Name}");
            MessageBox.Show(
                AppMessages.SharedFilesUnreadable(shared, exception.Message),
                AppMessages.Title,
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return 2;
        }
        using (host)
        {
            host.ExitRequested += Application.ExitThread;
            host.Start();
            Application.Run();
        }
        return 0;
    }
}
