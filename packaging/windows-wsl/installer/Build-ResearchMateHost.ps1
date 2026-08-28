param(
    [string]$DotNetExecutable = "dotnet",
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$installerDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageDirectory = Split-Path -Parent $installerDirectory
$project = Join-Path $packageDirectory "host\ResearchMate.WindowsWslHost.csproj"
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $packageDirectory "artifacts\win-x64"
}

if (-not (Test-Path -LiteralPath $project -PathType Leaf)) {
    throw "Windows host project not found: $project"
}

$staging = $OutputDirectory + ".staging"
if (Test-Path -LiteralPath $staging) {
    Remove-Item -LiteralPath $staging -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $staging | Out-Null

try {
    & $DotNetExecutable publish $project `
        --configuration Release `
        --runtime win-x64 `
        --self-contained true `
        --output $staging `
        -p:PublishReadyToRun=false `
        -p:PublishTrimmed=false
    if ($LASTEXITCODE -ne 0) {
        throw "dotnet publish failed with exit code $LASTEXITCODE"
    }

    $hostExe = Join-Path $staging "ResearchMate.WindowsWslHost.exe"
    $loader = Join-Path $staging "WebView2Loader.dll"
    if (-not (Test-Path -LiteralPath $hostExe -PathType Leaf) -or
        -not (Test-Path -LiteralPath $loader -PathType Leaf)) {
        throw "Published host is incomplete"
    }

    if (Test-Path -LiteralPath $OutputDirectory) {
        Remove-Item -LiteralPath $OutputDirectory -Recurse -Force
    }
    Move-Item -LiteralPath $staging -Destination $OutputDirectory
    Write-Output "Published self-contained host: $OutputDirectory"
}
catch {
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
    throw
}
