using System.Text.Json;

namespace ResearchMate.WindowsWslHost;

internal static class RuntimeInstallationInfo
{
    public static string Build(HostOptions options)
    {
        var installDirectory = AppContext.BaseDirectory.TrimEnd(
            Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        var localState = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "ResearchMate");
        var shortcut = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
            "ResearchMate.lnk");
        return JsonSerializer.Serialize(new
        {
            schema_version = 1,
            platform = "windows_wsl",
            platform_label = "Windows + WSL 桌面",
            paths = new[]
            {
                new { label = "Windows 宿主安装目录", path = installDirectory, ownership = "application" },
                new { label = "Windows 配置、日志与 WebView 状态", path = localState, ownership = "application_state" },
                new { label = "Windows 桌面快捷方式", path = shortcut, ownership = "application" },
                new { label = "WSL 源码", path = options.ProjectPath, ownership = "user" },
                new { label = "WSL 前端依赖", path = $"{options.ProjectPath.TrimEnd('/')}/src/frontend/node_modules", ownership = "rebuildable" },
                new { label = "WSL 前端构建", path = $"{options.ProjectPath.TrimEnd('/')}/src/frontend/dist", ownership = "rebuildable" },
                new { label = "WSL Windows 宿主构建产物", path = $"{options.ProjectPath.TrimEnd('/')}/packaging/windows-wsl/artifacts/win-x64", ownership = "rebuildable" },
                new { label = "工作区与用户资产", path = $"{options.ProjectPath.TrimEnd('/')}/src/data", ownership = "user_data" },
                new { label = "WSL Conda 可执行文件", path = options.CondaExecutable, ownership = "external" },
            },
            uninstall = new
            {
                available = true,
                summary = "关闭窗口后，可从 Windows“已安装的应用”卸载；不会删除 WSL 源码、环境或工作区。",
                guide_path = Path.Combine(installDirectory, "uninstall-guide-zh-CN.txt"),
            },
        });
    }
}
