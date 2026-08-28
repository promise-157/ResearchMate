using System.Text.Json;
using System.Text.Json.Serialization;

namespace ResearchMate.WindowsWslHost;

public sealed record RuntimeEvent
{
    [JsonPropertyName("event")]
    public string Event { get; init; } = "";

    [JsonPropertyName("instance_id")]
    public string InstanceId { get; init; } = "";

    [JsonPropertyName("message")]
    public string? Message { get; init; }

    [JsonPropertyName("process_group_id")]
    public int? ProcessGroupId { get; init; }

    [JsonPropertyName("pid")]
    public int? Pid { get; init; }

    [JsonPropertyName("exit_code")]
    public int? ExitCode { get; init; }

    [JsonPropertyName("requested")]
    public bool? Requested { get; init; }

    public static RuntimeEvent? Parse(string line)
    {
        try
        {
            return JsonSerializer.Deserialize<RuntimeEvent>(line);
        }
        catch (JsonException)
        {
            return null;
        }
    }
}
