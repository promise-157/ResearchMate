using ResearchMate.WindowsWslHost;
using ResearchMate.WindowsWslHost.Tests;

if (args.Length > 0 && args[0] == "--real-wsl")
{
    if (args.Length != 4)
    {
        throw new ArgumentException(
            "Usage: --real-wsl <distro> <project-path> <conda-executable>");
    }
    await RealWslProbe.RunAsync(args[1], args[2], args[3]);
    return;
}

if (args.Length > 0 && args[0] == "--real-host")
{
    if (args.Length != 4)
    {
        throw new ArgumentException(
            "Usage: --real-host <distro> <project-path> <conda-executable>");
    }
    await RealHostProbe.RunAsync(args[1], args[2], args[3]);
    return;
}

static void Assert(bool condition, string message)
{
    if (!condition)
    {
        throw new InvalidOperationException(message);
    }
}

var options = HostOptions.Parse(new[]
{
    "--distro", "Fixture-Distro",
    "--project", "/fixture/project with spaces",
    "--conda-executable", "/fixture/miniconda/conda",
    "--conda-env", "researchmate-test",
    "--port", "8123",
});
Assert(options.Distro == "Fixture-Distro", "distro parsing failed");
Assert(options.ProjectPath == "/fixture/project with spaces", "project parsing failed");
Assert(options.CondaExecutable == "/fixture/miniconda/conda", "conda parsing failed");
Assert(options.Port == 8123, "port parsing failed");
Assert(options.SupervisorScript == "src/backend/desktop_runtime.py", "default supervisor failed");
Assert(options.AutoCloseSeconds is null, "auto close must be disabled by default");

var configPath = Path.Combine(Path.GetTempPath(), $"researchmate-config-{Guid.NewGuid():N}.json");
try
{
    File.WriteAllText(configPath, """
        {
          "schema_version": 1,
          "distro": "Config-Distro",
          "project_path": "/config/project",
          "conda_executable": "/config/conda",
          "conda_environment": "configured-env",
          "port": 8234
        }
        """);
    var configured = HostOptions.Parse(new[] { "--config", configPath });
    Assert(configured.Distro == "Config-Distro", "config distro failed");
    Assert(configured.ProjectPath == "/config/project", "config project failed");
    Assert(configured.CondaExecutable == "/config/conda", "config conda failed");
    Assert(configured.CondaEnvironment == "configured-env", "config environment failed");
    Assert(configured.Port == 8234, "config port failed");
}
finally
{
    File.Delete(configPath);
}

try
{
    HostOptions.Parse(new[]
    {
        "--distro", "Fixture", "--project", "relative/path",
        "--conda-executable", "/fixture/conda",
    });
    throw new InvalidOperationException("relative project path was accepted");
}
catch (ArgumentException)
{
}

try
{
    HostOptions.Parse(new[]
    {
        "--distro", "Fixture",
        "--project", "/fixture",
        "--conda-executable", "/fixture/conda",
        "--conda-env", "bad;command",
    });
    throw new InvalidOperationException("unsafe conda environment was accepted");
}
catch (ArgumentException)
{
}

var instanceId = "0123456789abcdef0123456789abcdef";
var start = WslCommandBuilder.BuildSupervisor(options, instanceId);
Assert(start.FileName == "wsl.exe", "unexpected supervisor executable");
Assert(!start.UseShellExecute && start.CreateNoWindow, "supervisor must be hidden and redirected");
Assert(start.RedirectStandardInput, "supervisor stdin must be owned by host");
Assert(start.ArgumentList.Contains("/fixture/project with spaces"), "project path was not an argument");
Assert(start.ArgumentList.Contains("/fixture/miniconda/conda"), "conda path was not an argument");
Assert(start.ArgumentList.Contains(instanceId), "instance id was not forwarded");
var runtimeInfoIndex = start.ArgumentList.IndexOf("--runtime-info-json");
Assert(runtimeInfoIndex >= 0, "runtime installation info was not forwarded");
Assert(
    start.ArgumentList[runtimeInfoIndex + 1].Contains("windows_wsl"),
    "runtime installation platform is missing");

var identitySuffix = Guid.NewGuid().ToString("N");
var instanceOptions = options with { ProjectPath = options.ProjectPath + identitySuffix };
var firstCoordinator = new SingleInstanceCoordinator(instanceOptions);
var waitingCoordinator = new SingleInstanceCoordinator(instanceOptions);
try
{
    Assert(firstCoordinator.IsPrimary, "first coordinator did not own the mutex");
    Assert(!waitingCoordinator.IsPrimary, "waiting coordinator unexpectedly owned the mutex");
    firstCoordinator.Dispose();
    Assert(
        waitingCoordinator.TryAcquirePrimary(TimeSpan.FromSeconds(1)),
        "waiting coordinator did not take ownership after the first instance exited");
}
finally
{
    waitingCoordinator.Dispose();
}

var fixtureOptions = HostOptions.Parse(new[]
{
    "--distro", "Fixture-Distro",
    "--project", "/fixture/project",
    "--conda-executable", "/fixture/conda",
    "--test-supervisor-script", "tests/fixtures/desktop_runtime_harness.py",
    "--auto-close-seconds", "5",
});
Assert(
    fixtureOptions.SupervisorScript == "tests/fixtures/desktop_runtime_harness.py",
    "debug fixture supervisor was not accepted");
Assert(fixtureOptions.AutoCloseSeconds == 5, "debug auto-close was not accepted");

var killer = WslCommandBuilder.BuildForceKill(options, 4321);
Assert(killer.ArgumentList[^1] == "-4321", "force kill must target exact process group");
Assert(killer.ArgumentList.Contains("--"), "force kill requires option boundary");

try
{
    WslCommandBuilder.BuildForceKill(options, 1);
    throw new InvalidOperationException("unsafe process group was accepted");
}
catch (ArgumentOutOfRangeException)
{
}

var parsedEvent = RuntimeEvent.Parse(
    "{\"event\":\"backend_spawned\",\"instance_id\":\"" + instanceId +
    "\",\"process_group_id\":4321}");
Assert(parsedEvent?.Event == "backend_spawned", "runtime event parsing failed");
Assert(parsedEvent?.ProcessGroupId == 4321, "runtime process group parsing failed");
Assert(RuntimeEvent.Parse("not-json") is null, "invalid protocol JSON was accepted");

var iconFixture = Path.Combine(Path.GetTempPath(), $"researchmate-icon-{Guid.NewGuid():N}.ico");
try
{
    File.WriteAllBytes(iconFixture, new byte[]
    {
        0, 0, 1, 0, 1, 0,
        16, 16, 0, 0, 1, 0, 32, 0, 4, 0, 0, 0, 22, 0, 0, 0,
        0, 0, 0, 0,
    });
    ShortcutIconManager.ValidateIcon(iconFixture);
    File.WriteAllBytes(iconFixture, new byte[] { 0, 0, 2, 0, 1, 0 });
    try
    {
        ShortcutIconManager.ValidateIcon(iconFixture);
        throw new InvalidOperationException("invalid ICO header was accepted");
    }
    catch (InvalidDataException)
    {
    }
}
finally
{
    File.Delete(iconFixture);
}

Console.WriteLine("Windows WSL host offline contract tests passed.");
