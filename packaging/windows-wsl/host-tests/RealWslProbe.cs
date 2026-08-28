using System.Diagnostics;
using System.Net;
using System.Text.Json;

namespace ResearchMate.WindowsWslHost.Tests;

internal static class RealWslProbe
{
    private const string InstanceId = "0123456789abcdef0123456789abcdef";
    public static async Task RunAsync(string distro, string projectPath, string condaExecutable)
    {
        var markerRoot = $"/tmp/researchmate-desktop-probe-{Environment.ProcessId}";
        var portBase = 20000 + Environment.ProcessId % 30000;
        await RunWslAsync(distro, "/bin/rm", "-f", "--",
            markerRoot + "-explicit", markerRoot + "-eof", markerRoot + "-forced");
        try
        {
            await RunExplicitShutdownAsync(
                distro, projectPath, condaExecutable, markerRoot + "-explicit", portBase);
            await RunEofShutdownAsync(
                distro, projectPath, condaExecutable, markerRoot + "-eof", portBase + 1);
            await RunForcedShutdownAsync(
                distro, projectPath, condaExecutable, markerRoot + "-forced", portBase + 2);
            await RunPortConflictAsync(
                distro, projectPath, condaExecutable, markerRoot + "-conflict", portBase + 3);
            await RunSupervisorCrashAsync(
                distro, projectPath, condaExecutable, markerRoot + "-crash", portBase + 4);
        }
        finally
        {
            await RunWslAsync(distro, "/bin/rm", "-f", "--",
                markerRoot + "-explicit", markerRoot + "-eof", markerRoot + "-forced",
                markerRoot + "-conflict", markerRoot + "-crash");
        }
        Console.WriteLine(
            "Real WSL shutdown, EOF, forced group, port conflict and supervisor crash probes passed.");
    }

    private static async Task RunPortConflictAsync(
        string distro, string projectPath, string condaExecutable, string marker, int port)
    {
        using var owner = StartProbe(
            distro, projectPath, condaExecutable, marker, port, ignoreTerm: false);
        try
        {
            await WaitForSpawnAndHealthAsync(owner, port);
            using var contender = StartProbe(
                distro, projectPath, condaExecutable, marker + "-unused", port, ignoreTerm: false);
            try
            {
                var output = await contender.StandardOutput.ReadToEndAsync();
                var error = await contender.StandardError.ReadToEndAsync();
                using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(8));
                await contender.WaitForExitAsync(timeout.Token);
                Ensure(contender.ExitCode == 1, "Port-conflict contender did not fail", error);
                Ensure(output.Contains("startup_failed", StringComparison.Ordinal),
                    "Port-conflict startup_failed event is missing", output);
                using var http = new HttpClient(new HttpClientHandler { UseProxy = false });
                using var response = await http.GetAsync($"http://127.0.0.1:{port}/api/health");
                Ensure(response.StatusCode == HttpStatusCode.OK,
                    "Port owner was disrupted by the contender");
            }
            finally
            {
                await StopFailedProbeAsync(contender);
            }
            owner.StandardInput.Close();
            var ownerResult = await WaitForExitAsync(owner);
            Ensure(ownerResult.ExitCode == 0, "Port owner failed during cleanup", ownerResult.Error);
            Ensure(await WslPathExistsAsync(distro, marker),
                "Port owner did not receive its own shutdown");
        }
        finally
        {
            await StopFailedProbeAsync(owner);
        }
    }

    private static async Task RunSupervisorCrashAsync(
        string distro, string projectPath, string condaExecutable, string marker, int port)
    {
        using var probe = StartProbe(
            distro, projectPath, condaExecutable, marker, port, ignoreTerm: false);
        try
        {
            var identity = await WaitForSpawnAndHealthAsync(probe, port);
            Ensure(identity.SupervisorPid > 1, "Supervisor PID was not reported");
            await RunWslAsync(
                distro, "/bin/kill", "-KILL", "--", identity.SupervisorPid.ToString());
            var result = await WaitForExitAsync(probe);
            Ensure(result.ExitCode != 0, "Killed supervisor unexpectedly reported success");

            var deadline = DateTime.UtcNow.AddSeconds(5);
            while (DateTime.UtcNow < deadline && !await WslPathExistsAsync(distro, marker))
            {
                await Task.Delay(100);
            }
            Ensure(await WslPathExistsAsync(distro, marker),
                "Backend did not receive parent-death SIGTERM after supervisor crash");
        }
        finally
        {
            await StopFailedProbeAsync(probe);
        }
    }

    private static async Task RunExplicitShutdownAsync(
        string distro, string projectPath, string condaExecutable, string marker, int port)
    {
        using var probe = StartProbe(
            distro, projectPath, condaExecutable, marker, port, ignoreTerm: false);
        try
        {
            await WaitForSpawnAndHealthAsync(probe, port);
            var frame = JsonSerializer.Serialize(new
            {
                command = "shutdown",
                instance_id = InstanceId,
                reason = "windows_probe",
            });
            await probe.StandardInput.WriteLineAsync(frame);
            await probe.StandardInput.FlushAsync();
            var result = await WaitForExitAsync(probe);
            Ensure(result.ExitCode == 0, "Explicit shutdown returned a failure", result.Error);
            Ensure(await WslPathExistsAsync(distro, marker), "Explicit SIGTERM marker is missing");
        }
        finally
        {
            await StopFailedProbeAsync(probe);
        }
    }

    private static async Task RunEofShutdownAsync(
        string distro, string projectPath, string condaExecutable, string marker, int port)
    {
        using var probe = StartProbe(
            distro, projectPath, condaExecutable, marker, port, ignoreTerm: false);
        try
        {
            await WaitForSpawnAndHealthAsync(probe, port);
            probe.StandardInput.Close();
            var result = await WaitForExitAsync(probe);
            Ensure(result.ExitCode == 0, "EOF shutdown returned a failure", result.Error);
            Ensure(await WslPathExistsAsync(distro, marker), "EOF SIGTERM marker is missing");
        }
        finally
        {
            await StopFailedProbeAsync(probe);
        }
    }

    private static async Task RunForcedShutdownAsync(
        string distro, string projectPath, string condaExecutable, string marker, int port)
    {
        using var probe = StartProbe(
            distro, projectPath, condaExecutable, marker, port, ignoreTerm: true);
        try
        {
            await WaitForSpawnAndHealthAsync(probe, port);
            probe.StandardInput.Close();
            var result = await WaitForExitAsync(probe);
            Ensure(result.ExitCode == 0, "Forced shutdown returned a failure", result.Error);
            Ensure(result.Output.Contains("shutdown_forced", StringComparison.Ordinal),
                "Forced shutdown event was not emitted", result.Output);
            Ensure(!await WslPathExistsAsync(distro, marker),
                "SIGTERM-ignoring fixture unexpectedly wrote a graceful marker");
        }
        finally
        {
            await StopFailedProbeAsync(probe);
        }
    }

    private static Process StartProbe(
        string distro,
        string projectPath,
        string condaExecutable,
        string marker,
        int port,
        bool ignoreTerm)
    {
        var startInfo = WslStartInfo(distro);
        startInfo.RedirectStandardInput = true;
        startInfo.RedirectStandardOutput = true;
        startInfo.RedirectStandardError = true;
        foreach (var argument in new[]
        {
            "--cd", projectPath,
            "--exec", condaExecutable, "run", "--no-capture-output", "-n", "researchmate",
            "python", "tests/fixtures/desktop_runtime_harness.py",
            "--instance-id", InstanceId, "--port", port.ToString(), "--marker", marker,
            "--graceful-timeout", "0.4",
        })
        {
            startInfo.ArgumentList.Add(argument);
        }
        if (ignoreTerm)
        {
            startInfo.ArgumentList.Add("--ignore-term");
        }
        var process = new Process { StartInfo = startInfo };
        Ensure(process.Start(), "Unable to start the WSL lifecycle probe");
        return process;
    }

    private static async Task<(int SupervisorPid, int ProcessGroupId)>
        WaitForSpawnAndHealthAsync(Process probe, int port)
    {
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(25));
        int? supervisorPid = null;
        int? processGroupId = null;
        while (true)
        {
            var line = await probe.StandardOutput.ReadLineAsync(timeout.Token);
            if (line is null)
            {
                throw new InvalidOperationException(
                    "Probe exited before backend_spawned: " + await probe.StandardError.ReadToEndAsync());
            }
            var runtimeEvent = RuntimeEvent.Parse(line);
            if (runtimeEvent?.Event == "supervisor_started")
            {
                supervisorPid = runtimeEvent.Pid;
            }
            if (runtimeEvent?.Event == "startup_failed")
            {
                throw new InvalidOperationException(
                    "Supervisor startup failed: " + (runtimeEvent.Message ?? line));
            }
            if (runtimeEvent?.Event == "backend_spawned")
            {
                processGroupId = runtimeEvent.ProcessGroupId;
                break;
            }
        }

        using var http = new HttpClient(new HttpClientHandler { UseProxy = false });
        while (true)
        {
            timeout.Token.ThrowIfCancellationRequested();
            try
            {
                using var response = await http.GetAsync(
                    $"http://127.0.0.1:{port}/api/health", timeout.Token);
                if (response.StatusCode == HttpStatusCode.OK)
                {
                    var supervisorPidValue = supervisorPid
                        ?? throw new InvalidOperationException("Supervisor PID event is missing");
                    var processGroupIdValue = processGroupId
                        ?? throw new InvalidOperationException(
                            "Backend process-group event is missing");
                    Ensure(supervisorPidValue > 1, "Supervisor PID event is invalid");
                    Ensure(processGroupIdValue > 1, "Backend process-group event is invalid");
                    return (supervisorPidValue, processGroupIdValue);
                }
            }
            catch (HttpRequestException)
            {
            }
            await Task.Delay(100, timeout.Token);
        }
    }

    private static async Task StopFailedProbeAsync(Process process)
    {
        if (process.HasExited)
        {
            return;
        }
        try
        {
            process.StandardInput.Close();
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(3));
            await process.WaitForExitAsync(timeout.Token);
        }
        catch (OperationCanceledException)
        {
            process.Kill(entireProcessTree: true);
            await process.WaitForExitAsync();
        }
        catch (InvalidOperationException)
        {
            // The process exited between the state check and cleanup.
        }
    }

    private static async Task<(int ExitCode, string Output, string Error)> WaitForExitAsync(
        Process process)
    {
        var outputTask = process.StandardOutput.ReadToEndAsync();
        var errorTask = process.StandardError.ReadToEndAsync();
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(12));
        try
        {
            await process.WaitForExitAsync(timeout.Token);
        }
        catch (OperationCanceledException)
        {
            process.Kill(entireProcessTree: true);
            throw new InvalidOperationException("WSL lifecycle probe did not exit within 12 seconds");
        }
        return (process.ExitCode, await outputTask, await errorTask);
    }

    private static async Task<bool> WslPathExistsAsync(string distro, string path)
    {
        return await RunWslAsync(distro, "/usr/bin/test", "-e", path) == 0;
    }

    private static async Task<int> RunWslAsync(string distro, params string[] arguments)
    {
        var startInfo = WslStartInfo(distro);
        foreach (var argument in arguments)
        {
            startInfo.ArgumentList.Add(argument);
        }
        using var process = Process.Start(startInfo)
            ?? throw new InvalidOperationException("Unable to start wsl.exe");
        await process.WaitForExitAsync();
        return process.ExitCode;
    }

    private static ProcessStartInfo WslStartInfo(string distro)
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

    private static void Ensure(bool condition, string message, string? detail = null)
    {
        if (!condition)
        {
            throw new InvalidOperationException(
                string.IsNullOrWhiteSpace(detail) ? message : $"{message}: {detail}");
        }
    }
}
