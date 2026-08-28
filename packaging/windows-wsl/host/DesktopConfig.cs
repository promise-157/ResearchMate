using System.Text.Json;
using System.Text.Json.Serialization;

namespace ResearchMate.WindowsWslHost;

public sealed record DesktopConfig(
    [property: JsonPropertyName("schema_version")] int SchemaVersion,
    [property: JsonPropertyName("distro")] string Distro,
    [property: JsonPropertyName("project_path")] string ProjectPath,
    [property: JsonPropertyName("conda_executable")] string CondaExecutable,
    [property: JsonPropertyName("conda_environment")] string CondaEnvironment,
    [property: JsonPropertyName("port")] int Port)
{
    public static string DefaultPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "ResearchMate",
        "desktop-config.json");

    public static DesktopConfig Load(string path)
    {
        try
        {
            var json = File.ReadAllText(path);
            var config = JsonSerializer.Deserialize<DesktopConfig>(json);
            if (config is null)
            {
                throw new InvalidDataException("配置文件内容为空");
            }
            if (config.SchemaVersion != 1)
            {
                throw new InvalidDataException($"不支持配置版本 {config.SchemaVersion}");
            }
            return config;
        }
        catch (Exception error) when (error is IOException or JsonException or InvalidDataException)
        {
            throw new ArgumentException($"无法读取桌面配置 {path}：{error.Message}", error);
        }
    }
}
