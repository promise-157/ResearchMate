namespace ResearchMate.WindowsWslHost;

internal static class Program
{
    [STAThread]
    private static void Main(string[] args)
    {
        ApplicationConfiguration.Initialize();

        HostOptions options;
        try
        {
            options = HostOptions.Parse(args);
        }
        catch (ArgumentException error)
        {
            MessageBox.Show(
                error.Message + "\n\n示例：\n" +
                "请重新运行 ResearchMate 配置向导，或使用 --config <配置文件路径>。",
                "ResearchMate 配置错误",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return;
        }

        using var singleInstance = new SingleInstanceCoordinator(options);
        if (!singleInstance.IsPrimary)
        {
            var activated = false;
            for (var attempt = 0; attempt < 12 && !singleInstance.IsPrimary; attempt++)
            {
                activated = singleInstance.SendActivationAsync().GetAwaiter().GetResult();
                if (activated)
                {
                    return;
                }
                if (singleInstance.TryAcquirePrimary(TimeSpan.Zero))
                {
                    break;
                }
                Thread.Sleep(100);
            }
            if (!singleInstance.IsPrimary)
            {
                return;
            }
        }

        using var log = new LocalLog();
        using var form = new MainForm(options, log);
        _ = singleInstance.ListenAsync(form.ActivateExistingWindow);
        Application.Run(form);
    }
}
