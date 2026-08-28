using System.IO.Pipes;
using System.Security.Cryptography;
using System.Text;

namespace ResearchMate.WindowsWslHost;

internal sealed class SingleInstanceCoordinator : IDisposable
{
    private readonly Mutex _mutex;
    private readonly string _pipeName;
    private readonly bool _ownsMutex;
    private readonly CancellationTokenSource _cancellation = new();

    public bool IsPrimary => _ownsMutex;

    public SingleInstanceCoordinator(HostOptions options)
    {
        var identity = $"{options.Distro}\n{options.ProjectPath}";
        var hash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(identity)))[..20];
        _pipeName = $"ResearchMate.WindowsWsl.{hash}";
        _mutex = new Mutex(true, $"Local\\{_pipeName}", out _ownsMutex);
    }

    public async Task SendActivationAsync()
    {
        try
        {
            await using var client = new NamedPipeClientStream(
                ".", _pipeName, PipeDirection.Out, PipeOptions.Asynchronous);
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(2));
            await client.ConnectAsync(timeout.Token);
            await using var writer = new StreamWriter(client, Encoding.UTF8) { AutoFlush = true };
            await writer.WriteLineAsync("activate");
        }
        catch (IOException)
        {
            // The first instance may still be creating its activation pipe.
        }
        catch (OperationCanceledException)
        {
            // Do not create a second backend if activation times out.
        }
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
        _cancellation.Dispose();
        if (_ownsMutex)
        {
            _mutex.ReleaseMutex();
        }
        _mutex.Dispose();
    }
}
