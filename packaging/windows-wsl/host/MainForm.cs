using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

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
