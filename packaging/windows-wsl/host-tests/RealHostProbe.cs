using System.Diagnostics;
using System.Net;

namespace ResearchMate.WindowsWslHost.Tests;

internal static class RealHostProbe
{
    public static async Task RunAsync(string distro, string projectPath, string condaExecutable)
    {
        var port = 50000 + Environment.ProcessId % 10000;
        var marker = "/tmp/researchmate-desktop-host-fixture.marker";
        await RunWslAsync(distro, "/bin/rm", "-f", "--", marker);
        using var first = StartHost(
            distro, projectPath, condaExecutable, port, autoCloseSeconds: 18);
        try
        {
            await WaitForHealthAsync(port, first);
            using var second = StartHost(
                distro, projectPath, condaExecutable, port, autoCloseSeconds: 18);
            using (var secondTimeout = new CancellationTokenSource(TimeSpan.FromSeconds(5)))
            {
                await second.WaitForExitAsync(secondTimeout.Token);
            }
            Ensure(second.ExitCode == 0, "Second desktop host did not exit cleanly");
            Ensure(!first.HasExited, "Second desktop host disrupted the primary window");

            var conflictProjectIdentity = projectPath.TrimEnd('/') + "/.";
            var conflictDuration = Stopwatch.StartNew();
            using var conflict = StartHost(
                distro,
                conflictProjectIdentity,
                condaExecutable,
                port,
                autoCloseSeconds: 6);
            using (var conflictTimeout = new CancellationTokenSource(TimeSpan.FromSeconds(12)))
            {
                await conflict.WaitForExitAsync(conflictTimeout.Token);
            }
            conflictDuration.Stop();
            Ensure(conflict.ExitCode == 0, "Port-conflict desktop window did not close cleanly");
            Ensure(conflictDuration.Elapsed >= TimeSpan.FromSeconds(5),
                "Port-conflict desktop window was not kept visible");
            Ensure(!first.HasExited, "Port-conflict desktop window disrupted the primary window");
            Ensure(await PortIsHealthyAsync(port),
                "Port-conflict desktop window disrupted the primary backend");

            using (var firstTimeout = new CancellationTokenSource(TimeSpan.FromSeconds(15)))
            {
                await first.WaitForExitAsync(firstTimeout.Token);
            }
            Ensure(first.ExitCode == 0, "Primary desktop host did not close cleanly");
            Ensure(await WslPathExistsAsync(distro, marker),
                "Primary window close did not deliver SIGTERM to its backend");
            Ensure(!await PortIsHealthyAsync(port), "Primary backend remains after window close");

            using var restarted = StartHost(
                distro, projectPath, condaExecutable, port, autoCloseSeconds: 6);
            await WaitForHealthAsync(port, restarted);
            using (var restartedTimeout = new CancellationTokenSource(TimeSpan.FromSeconds(12)))
            {
                await restarted.WaitForExitAsync(restartedTimeout.Token);
            }
            Ensure(restarted.ExitCode == 0, "Desktop host did not restart after primary close");
            Ensure(!await PortIsHealthyAsync(port), "Restarted backend remains after window close");
        }
        finally
        {
            if (!first.HasExited)
            {
                first.Kill(entireProcessTree: true);
                await first.WaitForExitAsync();
            }
            await RunWslAsync(distro, "/bin/rm", "-f", "--", marker);
        }
        Console.WriteLine("Real WebView2 single-instance and window-close probe passed.");
    }

    private static Process StartHost(
        string distro,
        string projectPath,
        string condaExecutable,
        int port,
        int autoCloseSeconds)
    {
        var dotnet = Environment.ProcessPath
            ?? throw new InvalidOperationException("Unable to resolve dotnet host path");
        var hostDll = Path.Combine(AppContext.BaseDirectory, "ResearchMate.WindowsWslHost.dll");
        var startInfo = new ProcessStartInfo
        {
            FileName = dotnet,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (var argument in new[]
        {
            hostDll,
            "--distro", distro,
            "--project", projectPath,
            "--conda-executable", condaExecutable,
            "--port", port.ToString(),
            "--test-supervisor-script", "tests/fixtures/desktop_runtime_harness.py",
            "--auto-close-seconds", autoCloseSeconds.ToString(),
        })
        {
            startInfo.ArgumentList.Add(argument);
        }
        var process = new Process { StartInfo = startInfo };
        Ensure(process.Start(), "Unable to start desktop host probe");
        return process;
    }

    private static async Task WaitForHealthAsync(int port, Process process)
    {
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(25));
        while (true)
        {
            timeout.Token.ThrowIfCancellationRequested();
            Ensure(!process.HasExited, "Desktop host exited before health check");
            if (await PortIsHealthyAsync(port, timeout.Token))
            {
                return;
            }
            await Task.Delay(100, timeout.Token);
        }
    }

    private static async Task<bool> PortIsHealthyAsync(
        int port, CancellationToken cancellationToken = default)
    {
        using var http = new HttpClient(new HttpClientHandler { UseProxy = false })
        {
            Timeout = TimeSpan.FromSeconds(1),
        };
        try
        {
            using var response = await http.GetAsync(
                $"http://127.0.0.1:{port}/api/health", cancellationToken);
            return response.StatusCode == HttpStatusCode.OK;
        }
        catch (HttpRequestException)
        {
            return false;
        }
        catch (TaskCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return false;
        }
    }

    private static async Task<bool> WslPathExistsAsync(string distro, string path)
    {
        return await RunWslAsync(distro, "/usr/bin/test", "-e", path) == 0;
    }

    private static async Task<int> RunWslAsync(string distro, params string[] arguments)
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = "wsl.exe",
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        startInfo.ArgumentList.Add("--distribution");
        startInfo.ArgumentList.Add(distro);
        foreach (var argument in arguments)
        {
            startInfo.ArgumentList.Add(argument);
        }
        using var process = Process.Start(startInfo)
            ?? throw new InvalidOperationException("Unable to start wsl.exe");
        await process.WaitForExitAsync();
        return process.ExitCode;
    }

    private static void Ensure(bool condition, string message)
    {
        if (!condition)
        {
            throw new InvalidOperationException(message);
        }
    }
}
