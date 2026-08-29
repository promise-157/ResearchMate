using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;
using System.Text.Json;

namespace ResearchMate.WindowsWslHost;

internal sealed class MainForm : Form
{
    private readonly HostOptions _options;
    private readonly LocalLog _log;
    private readonly WebView2 _webView = new() { Dock = DockStyle.Fill, Visible = false };
    private readonly Label _status = new()
    {
        Dock = DockStyle.Fill,
        Text = "正在启动 ResearchMate…",
        TextAlign = ContentAlignment.MiddleCenter,
        Font = new Font(SystemFonts.MessageBoxFont?.FontFamily ?? FontFamily.GenericSansSerif, 12),
    };
    private readonly CancellationTokenSource _lifetime = new();
    private WslRuntime? _runtime;
    private bool _allowClose;

    public MainForm(HostOptions options, LocalLog log)
    {
        _options = options;
        _log = log;
        Text = "ResearchMate";
        Width = 1280;
        Height = 820;
        MinimumSize = new Size(900, 600);
        StartPosition = FormStartPosition.CenterScreen;
        Controls.Add(_webView);
        Controls.Add(_status);
        Shown += async (_, _) => await StartRuntimeAsync();
        FormClosing += OnFormClosing;
        if (_options.AutoCloseSeconds is { } seconds)
        {
            var timer = new System.Windows.Forms.Timer { Interval = seconds * 1000 };
            timer.Tick += (_, _) =>
            {
                timer.Stop();
                timer.Dispose();
                Close();
            };
            timer.Start();
        }
    }

    public void ActivateExistingWindow()
    {
        if (InvokeRequired)
        {
            BeginInvoke(ActivateExistingWindow);
            return;
        }
        if (WindowState == FormWindowState.Minimized)
        {
            WindowState = FormWindowState.Normal;
        }
        Show();
        Activate();
        BringToFront();
    }

    private async Task StartRuntimeAsync()
    {
        try
        {
            _runtime = new WslRuntime(_options, _log);
            _runtime.Failed += ShowRuntimeFailure;
            await _runtime.StartAsync(_lifetime.Token);
            var webViewRoot = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "ResearchMate",
                "webview2");
            var environment = await CoreWebView2Environment.CreateAsync(
                userDataFolder: webViewRoot);
            await _webView.EnsureCoreWebView2Async(environment);
            _webView.CoreWebView2.Settings.AreDevToolsEnabled = false;
            _webView.CoreWebView2.Settings.IsStatusBarEnabled = false;
            _webView.CoreWebView2.WebMessageReceived += OnWebMessageReceived;
            _webView.Source = _runtime.ApplicationUri;
            _status.Visible = false;
            _webView.Visible = true;
            _log.Write("host", "WEBVIEW_READY - local ResearchMate page loaded");
        }
        catch (OperationCanceledException) when (_lifetime.IsCancellationRequested)
        {
            _log.Write("host", "窗口关闭取消了尚未完成的启动");
        }
        catch (Exception error)
        {
            _log.Write("host", $"启动失败：{error.Message}");
            ShowRuntimeFailure($"ResearchMate 启动失败\n\n{error.Message}\n\n日志：{_log.Path}");
        }
    }

    private void OnWebMessageReceived(object? sender, CoreWebView2WebMessageReceivedEventArgs eventArgs)
    {
        if (_runtime is null || !IsOwnedApplicationOrigin(eventArgs.Source, _runtime.ApplicationUri))
        {
            return;
        }
        try
        {
            using var document = JsonDocument.Parse(eventArgs.WebMessageAsJson);
            var type = document.RootElement.GetProperty("type").GetString();
            if (type == "select_shortcut_icon")
            {
                using var dialog = new OpenFileDialog
                {
                    Title = "选择 ResearchMate 快捷方式图标",
                    Filter = "Windows 图标 (*.ico)|*.ico",
                    CheckFileExists = true,
                    Multiselect = false,
                };
                if (dialog.ShowDialog(this) != DialogResult.OK)
                {
                    PostIconResult("cancelled", "已取消选择", null);
                    return;
                }
                var installedPath = ShortcutIconManager.ApplyCustomIcon(dialog.FileName);
                PostIconResult("ok", "快捷方式图标已更新", installedPath);
                return;
            }
            if (type == "reset_shortcut_icon")
            {
                ShortcutIconManager.RestoreDefaultIcon();
                PostIconResult("ok", "已恢复默认图标", Application.ExecutablePath);
            }
        }
        catch (Exception error)
        {
            _log.Write("host", $"更新快捷方式图标失败：{error.Message}");
            PostIconResult("error", error.Message, null);
        }
    }

    private static bool IsOwnedApplicationOrigin(string source, Uri applicationUri)
    {
        return Uri.TryCreate(source, UriKind.Absolute, out var sourceUri) &&
            sourceUri.Scheme == applicationUri.Scheme &&
            sourceUri.Host == applicationUri.Host &&
            sourceUri.Port == applicationUri.Port;
    }

    private void PostIconResult(string status, string message, string? path)
    {
        _webView.CoreWebView2.PostWebMessageAsJson(JsonSerializer.Serialize(new
        {
            type = "shortcut_icon_result",
            status,
            message,
            path,
        }));
    }

    private void ShowRuntimeFailure(string message)
    {
        if (InvokeRequired)
        {
            BeginInvoke(() => ShowRuntimeFailure(message));
            return;
        }
        _webView.Visible = false;
        _status.Text = message;
        _status.Visible = true;
    }

    private async void OnFormClosing(object? sender, FormClosingEventArgs eventArgs)
    {
        if (_allowClose)
        {
            return;
        }
        eventArgs.Cancel = true;
        _lifetime.Cancel();
        Enabled = false;
        _webView.Visible = false;
        _status.Text = "正在安全退出 ResearchMate…";
        _status.Visible = true;
        try
        {
            if (_runtime is not null)
            {
                await _runtime.DisposeAsync();
                _runtime = null;
            }
        }
        finally
        {
            _allowClose = true;
            _lifetime.Dispose();
            Close();
        }
    }
}
