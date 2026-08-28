using System.Text.RegularExpressions;

namespace ResearchMate.WindowsWslHost;

internal sealed class LocalLog : IDisposable
{
    private const long MaxLogBytes = 2 * 1024 * 1024;
    private static readonly Regex BearerPattern = new(
        "(?i)(authorization\\s*[:=]\\s*bearer\\s+)[^\\s]+",
        RegexOptions.CultureInvariant);
    private static readonly Regex KeyPattern = new(
        "(?i)(api[_-]?key\\s*[:=]\\s*)[^\\s,;]+",
        RegexOptions.CultureInvariant);
    private readonly StreamWriter _writer;
    private readonly object _gate = new();

    public string Path { get; }

    public LocalLog()
    {
        var root = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        var directory = System.IO.Path.Combine(root, "ResearchMate", "logs");
        Directory.CreateDirectory(directory);
        Path = System.IO.Path.Combine(directory, "desktop-host.log");
        if (File.Exists(Path) && new FileInfo(Path).Length > MaxLogBytes)
        {
            File.Move(Path, Path + ".previous", true);
        }
        _writer = new StreamWriter(
            new FileStream(Path, FileMode.Append, FileAccess.Write, FileShare.ReadWrite))
        {
            AutoFlush = true,
        };
    }

    public void Write(string source, string message)
    {
        var sanitized = BearerPattern.Replace(message, "$1[REDACTED]");
        sanitized = KeyPattern.Replace(sanitized, "$1[REDACTED]");
        lock (_gate)
        {
            _writer.WriteLine($"{DateTimeOffset.Now:O} [{source}] {sanitized}");
        }
    }

    public void Dispose() => _writer.Dispose();
}
