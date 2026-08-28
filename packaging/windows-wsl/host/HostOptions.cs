using System.Text.RegularExpressions;

namespace ResearchMate.WindowsWslHost;

public sealed record HostOptions(
    string Distro,
    string ProjectPath,
    string CondaExecutable,
    string CondaEnvironment,
    int Port,
    string SupervisorScript,
    int? AutoCloseSeconds)
{
    private static readonly Regex SafeName = new("^[A-Za-z0-9_.-]+$", RegexOptions.CultureInvariant);

    public static HostOptions Parse(IReadOnlyList<string> args)
    {
        if (args.Count == 0)
        {
            return FromConfig(DesktopConfig.Load(DesktopConfig.DefaultPath));
        }
        if (args.Count == 2 && args[0] == "--config")
        {
            return FromConfig(DesktopConfig.Load(args[1]));
        }

        string? distro = null;
        string? project = null;
        string? condaExecutable = null;
        string condaEnvironment = "researchmate";
        var port = 8000;
        var supervisorScript = "src/backend/desktop_runtime.py";
        int? autoCloseSeconds = null;

        for (var index = 0; index < args.Count; index++)
        {
            var argument = args[index];
            string NextValue()
            {
                if (++index >= args.Count)
                {
                    throw new ArgumentException($"参数 {argument} 缺少值");
                }
                return args[index];
            }

            switch (argument)
            {
                case "--distro":
                    distro = NextValue();
                    break;
                case "--project":
                    project = NextValue();
                    break;
                case "--conda-env":
                    condaEnvironment = NextValue();
                    break;
                case "--conda-executable":
                    condaExecutable = NextValue();
                    break;
                case "--port":
                    if (!int.TryParse(NextValue(), out port))
                    {
                        throw new ArgumentException("--port 必须是整数");
                    }
                    break;
#if DEBUG
                case "--test-supervisor-script":
                    supervisorScript = NextValue();
                    break;
                case "--auto-close-seconds":
                    if (!int.TryParse(NextValue(), out var parsedSeconds))
                    {
                        throw new ArgumentException("--auto-close-seconds 必须是整数");
                    }
                    autoCloseSeconds = parsedSeconds;
                    break;
#endif
                default:
                    throw new ArgumentException($"未知参数：{argument}");
            }
        }

        if (string.IsNullOrWhiteSpace(distro) || distro.Contains('\n') || distro.Contains('\r'))
        {
            throw new ArgumentException("必须通过 --distro 指定有效的 WSL 发行版");
        }
        if (string.IsNullOrWhiteSpace(project) || !project.StartsWith('/') ||
            project.Contains('\n') || project.Contains('\r'))
        {
            throw new ArgumentException("必须通过 --project 指定有效的 WSL 绝对项目路径");
        }
        if (!SafeName.IsMatch(condaEnvironment))
        {
            throw new ArgumentException("Conda 环境名只允许字母、数字、点、下划线和连字符");
        }
        if (string.IsNullOrWhiteSpace(condaExecutable) || !condaExecutable.StartsWith('/') ||
            condaExecutable.Contains('\n') || condaExecutable.Contains('\r'))
        {
            throw new ArgumentException(
                "必须通过 --conda-executable 指定有效的 WSL Conda 可执行文件绝对路径");
        }
        if (port is < 1 or > 65535)
        {
            throw new ArgumentException("端口必须在 1–65535 之间");
        }
        if (supervisorScript != "src/backend/desktop_runtime.py" &&
            supervisorScript != "tests/fixtures/desktop_runtime_harness.py")
        {
            throw new ArgumentException("测试 supervisor 路径不在允许范围内");
        }
        if (autoCloseSeconds is not null and (< 1 or > 30))
        {
            throw new ArgumentException("自动关闭时间必须在 1–30 秒之间");
        }

        return new HostOptions(
            distro,
            project,
            condaExecutable,
            condaEnvironment,
            port,
            supervisorScript,
            autoCloseSeconds);
    }

    private static HostOptions FromConfig(DesktopConfig config)
    {
        return Parse(new[]
        {
            "--distro", config.Distro,
            "--project", config.ProjectPath,
            "--conda-executable", config.CondaExecutable,
            "--conda-env", config.CondaEnvironment,
            "--port", config.Port.ToString(System.Globalization.CultureInfo.InvariantCulture),
        });
    }
}
