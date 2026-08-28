param(
    [switch]$RemoveLocalState
)

$ErrorActionPreference = "Stop"
$installDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$metadataPath = Join-Path $installDirectory "installation-manifest.json"
$shortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "ResearchMate.lnk"
$uninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ResearchMate"
$localState = Join-Path $env:LOCALAPPDATA "ResearchMate"
$configPath = Join-Path $localState "desktop-config.json"

$running = Get-Process -Name "ResearchMate.WindowsWslHost" -ErrorAction SilentlyContinue
if ($running) {
    throw "ResearchMate is still running. Close its window before uninstalling."
}

if (Test-Path -LiteralPath $metadataPath -PathType Leaf) {
    $metadata = Get-Content -LiteralPath $metadataPath -Raw | ConvertFrom-Json
    if ($metadata.shortcut_path) {
        $shortcut = [string]$metadata.shortcut_path
    }
}

if (Test-Path -LiteralPath $shortcut -PathType Leaf) {
    Remove-Item -LiteralPath $shortcut -Force
}
if (Test-Path -LiteralPath $uninstallKey) {
    Remove-Item -LiteralPath $uninstallKey -Recurse -Force
}
if (Test-Path -LiteralPath $configPath -PathType Leaf) {
    Remove-Item -LiteralPath $configPath -Force
}

if ($RemoveLocalState) {
    if (Test-Path -LiteralPath $localState) {
        Remove-Item -LiteralPath $localState -Recurse -Force
    }
}

Set-Location $env:TEMP
Remove-Item -LiteralPath $installDirectory -Recurse -Force
Write-Output "ResearchMate Windows host and desktop shortcut were removed."
Write-Output "WSL, Conda, source code, workspaces, assets and archives were not removed."
if (-not $RemoveLocalState) {
    Write-Output "Local logs/WebView state were preserved. Use -RemoveLocalState to remove them."
}
