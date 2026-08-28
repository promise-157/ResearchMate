using System.Diagnostics;

namespace ResearchMate.WindowsWslHost;

public static class WslCommandBuilder
{
    public static ProcessStartInfo BuildSupervisor(HostOptions options, string instanceId)
    {
        var startInfo = BaseWslCommand(options.Distro);
        startInfo.RedirectStandardInput = true;
        startInfo.RedirectStandardOutput = true;
        startInfo.RedirectStandardError = true;
        startInfo.ArgumentList.Add("--cd");
        startInfo.ArgumentList.Add(options.ProjectPath);
        startInfo.ArgumentList.Add("--exec");
        startInfo.ArgumentList.Add(options.CondaExecutable);
        startInfo.ArgumentList.Add("run");
        startInfo.ArgumentList.Add("--no-capture-output");
        startInfo.ArgumentList.Add("-n");
        startInfo.ArgumentList.Add(options.CondaEnvironment);
        startInfo.ArgumentList.Add("python");
        startInfo.ArgumentList.Add(options.SupervisorScript);
        startInfo.ArgumentList.Add("--instance-id");
        startInfo.ArgumentList.Add(instanceId);
        startInfo.ArgumentList.Add("--port");
        startInfo.ArgumentList.Add(options.Port.ToString(System.Globalization.CultureInfo.InvariantCulture));
        return startInfo;
    }

    public static ProcessStartInfo BuildForceKill(HostOptions options, int processGroupId)
    {
        if (processGroupId <= 1)
        {
            throw new ArgumentOutOfRangeException(nameof(processGroupId));
        }
        var startInfo = BaseWslCommand(options.Distro);
        startInfo.ArgumentList.Add("--exec");
        startInfo.ArgumentList.Add("/bin/kill");
        startInfo.ArgumentList.Add("-KILL");
        startInfo.ArgumentList.Add("--");
        startInfo.ArgumentList.Add($"-{processGroupId}");
        return startInfo;
    }

    private static ProcessStartInfo BaseWslCommand(string distro)
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = "wsl.exe",
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        startInfo.ArgumentList.Add("--distribution");
        startInfo.ArgumentList.Add(distro);
        return startInfo;
    }
}
