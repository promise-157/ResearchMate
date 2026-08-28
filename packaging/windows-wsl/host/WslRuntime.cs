using System.Diagnostics;
using System.Net;
using System.Text.Json;

namespace ResearchMate.WindowsWslHost;

internal sealed class WslRuntime : IAsyncDisposable
{
    private static readonly TimeSpan StartupTimeout = TimeSpan.FromSeconds(45);
    private static readonly TimeSpan ShutdownTimeout = TimeSpan.FromSeconds(20);
    private readonly HostOptions _options;
    private readonly string _instanceId = Guid.NewGuid().ToString("N");
    private readonly LocalLog _log;
    private readonly HttpClient _http;
    private Process? _process;
    private int? _processGroupId;
    private bool _shutdownRequested;

    public event Action<string>? Failed;

    public Uri ApplicationUri => new($"http://127.0.0.1:{_options.Port}/");

    public WslRuntime(HostOptions options, LocalLog log)
    {
        _options = options;
        _log = log;
        _http = new HttpClient(new HttpClientHandler { UseProxy = false })
        {
            Timeout = TimeSpan.FromSeconds(2),
        };
    }

    public async Task StartAsync(CancellationToken cancellationToken)
    {
        _process = new Process
        {
            StartInfo = WslCommandBuilder.BuildSupervisor(_options, _instanceId),
            EnableRaisingEvents = true,
        };
        _process.Exited += (_, _) =>
        {
            if (!_shutdownRequested)
            {
                Failed?.Invoke("WSL 后端进程意外退出，请查看本机日志");
            }
        };
        if (!_process.Start())
        {
            throw new InvalidOperationException("无法启动 wsl.exe");
        }

        _ = ReadEventsAsync(_process.StandardOutput);
        _ = ReadLogsAsync(_process.StandardError);

        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(StartupTimeout);
        while (true)
        {
            timeout.Token.ThrowIfCancellationRequested();
            if (_process.HasExited)
            {
                throw new InvalidOperationException("WSL supervisor 在健康检查完成前退出");
            }
            try
            {
                using var response = await _http.GetAsync(
                    new Uri(ApplicationUri, "api/health"), timeout.Token);
                if (response.StatusCode == HttpStatusCode.OK)
                {
                    return;
                }
            }
            catch (HttpRequestException)
            {
                // The backend is still starting.
            }
            catch (TaskCanceledException) when (!timeout.IsCancellationRequested)
            {
                // One bounded request timed out; continue until the overall deadline.
            }
            await Task.Delay(250, timeout.Token);
        }
    }

    public async Task StopAsync()
    {
        if (_process is null || _shutdownRequested)
        {
            return;
        }
        _shutdownRequested = true;
        try
        {
            if (!_process.HasExited)
            {
                var frame = JsonSerializer.Serialize(new
                {
                    command = "shutdown",
                    instance_id = _instanceId,
                    reason = "window_close",
                });
                await _process.StandardInput.WriteLineAsync(frame);
                await _process.StandardInput.FlushAsync();
                _process.StandardInput.Close();
            }

            using var timeout = new CancellationTokenSource(ShutdownTimeout);
            await _process.WaitForExitAsync(timeout.Token);
        }
        catch (OperationCanceledException)
        {
            _log.Write("host", "优雅退出超时，准备结束已验证的 WSL 进程组");
            await ForceKillOwnedGroupAsync();
        }
        catch (IOException error)
        {
            _log.Write("host", $"关闭控制管道失败：{error.Message}");
            await ForceKillOwnedGroupAsync();
        }
    }

    private async Task ReadEventsAsync(StreamReader reader)
    {
        while (await reader.ReadLineAsync() is { } line)
        {
            var runtimeEvent = RuntimeEvent.Parse(line);
            if (runtimeEvent is null || runtimeEvent.InstanceId != _instanceId)
            {
                _log.Write("protocol", "忽略无效或实例不匹配的 supervisor 事件");
                continue;
            }
            if (runtimeEvent.Event == "backend_spawned")
            {
                _processGroupId = runtimeEvent.ProcessGroupId;
            }
            else if (runtimeEvent.Event == "startup_failed")
            {
                Failed?.Invoke(runtimeEvent.Message ?? "WSL supervisor 启动失败");
            }
            _log.Write("protocol", runtimeEvent.Event);
        }
    }

    private async Task ReadLogsAsync(StreamReader reader)
    {
        while (await reader.ReadLineAsync() is { } line)
        {
            _log.Write("backend", line);
        }
    }

    private async Task ForceKillOwnedGroupAsync()
    {
        if (_processGroupId is > 1)
        {
            using var killer = Process.Start(WslCommandBuilder.BuildForceKill(
                _options, _processGroupId.Value));
            if (killer is not null)
            {
                await killer.WaitForExitAsync();
            }
        }
        if (_process is { HasExited: false })
        {
            _process.Kill(entireProcessTree: true);
            await _process.WaitForExitAsync();
        }
    }

    public async ValueTask DisposeAsync()
    {
        await StopAsync();
        _process?.Dispose();
        _http.Dispose();
    }
}
