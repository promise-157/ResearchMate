using System.IO.Pipes;
using System.Security.Cryptography;
using System.Text;

namespace ResearchMate.WindowsWslHost;

internal sealed class SingleInstanceCoordinator : IDisposable
{
    private readonly Mutex _mutex;
    private readonly string _pipeName;
    private bool _ownsMutex;
    private readonly CancellationTokenSource _cancellation = new();

    public bool IsPrimary => _ownsMutex;

    public SingleInstanceCoordinator(HostOptions options)
    {
        var identity = $"{options.Distro}\n{options.ProjectPath}";
        var hash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(identity)))[..20];
        _pipeName = $"ResearchMate.WindowsWsl.{hash}";
        _mutex = new Mutex(true, $"Local\\{_pipeName}", out _ownsMutex);
    }

    public async Task<bool> SendActivationAsync()
    {
        try
        {
            await using var client = new NamedPipeClientStream(
                ".", _pipeName, PipeDirection.Out, PipeOptions.Asynchronous);
            using var timeout = new CancellationTokenSource(TimeSpan.FromMilliseconds(250));
            await client.ConnectAsync(timeout.Token);
            await using var writer = new StreamWriter(client, Encoding.UTF8) { AutoFlush = true };
            await writer.WriteLineAsync("activate");
            return true;
        }
        catch (IOException)
        {
            // The first instance may still be creating its activation pipe.
        }
        catch (OperationCanceledException)
        {
            // The primary may be exiting or may not have created its pipe yet.
        }
        return false;
    }

    public bool TryAcquirePrimary(TimeSpan timeout)
    {
        if (_ownsMutex)
        {
            return true;
        }
        try
        {
            _ownsMutex = _mutex.WaitOne(timeout);
        }
        catch (AbandonedMutexException)
        {
            _ownsMutex = true;
        }
        return _ownsMutex;
    }

    public async Task ListenAsync(Action activate)
    {
        while (!_cancellation.IsCancellationRequested)
        {
            try
            {
                await using var server = new NamedPipeServerStream(
                    _pipeName,
                    PipeDirection.In,
                    1,
                    PipeTransmissionMode.Byte,
                    PipeOptions.Asynchronous | PipeOptions.CurrentUserOnly);
                await server.WaitForConnectionAsync(_cancellation.Token);
                using var reader = new StreamReader(server, Encoding.UTF8);
                if (await reader.ReadLineAsync(_cancellation.Token) == "activate")
                {
                    activate();
                }
            }
            catch (OperationCanceledException) when (_cancellation.IsCancellationRequested)
            {
                return;
            }
            catch (IOException)
            {
                await Task.Delay(100, _cancellation.Token);
            }
        }
    }

    public void Dispose()
    {
        _cancellation.Cancel();
        if (_ownsMutex)
        {
            _mutex.ReleaseMutex();
        }
        _mutex.Dispose();
        _cancellation.Dispose();
    }
}
