param(
    [Parameter(Mandatory = $true)][string]$Distro,
    [Parameter(Mandatory = $true)][string]$ProjectPath,
    [Parameter(Mandatory = $true)][string]$CondaExecutable,
    [string]$CondaEnvironment = "researchmate",
    [int]$Port = 8000,
    [Parameter(Mandatory = $true)][string]$PublishedHostDirectory,
    [string]$InstallDirectory = ""
)

$ErrorActionPreference = "Stop"

function Assert-SafeValue([string]$Name, [string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value) -or $Value.Contains('"') -or
        $Value.Contains("`r") -or $Value.Contains("`n")) {
        throw "$Name contains an unsupported value"
    }
}

Assert-SafeValue "Distro" $Distro
Assert-SafeValue "ProjectPath" $ProjectPath
Assert-SafeValue "CondaExecutable" $CondaExecutable
if ($ProjectPath[0] -ne '/' -or $CondaExecutable[0] -ne '/') {
    throw "ProjectPath and CondaExecutable must be absolute WSL paths"
}
if ($CondaEnvironment -notmatch '^[A-Za-z0-9_.-]+$') {
    throw "CondaEnvironment contains unsupported characters"
}
if ($Port -lt 1 -or $Port -gt 65535) {
    throw "Port must be between 1 and 65535"
}

if (-not $InstallDirectory) {
    if (Test-Path -LiteralPath "D:\Apps" -PathType Container) {
        $InstallDirectory = "D:\Apps\ResearchMate"
    }
    else {
        $InstallDirectory = Join-Path $env:LOCALAPPDATA "Programs\ResearchMate"
    }
}

$publishedHost = Join-Path $PublishedHostDirectory "ResearchMate.WindowsWslHost.exe"
if (-not (Test-Path -LiteralPath $publishedHost -PathType Leaf)) {
    throw "Published host executable not found: $publishedHost"
}

& wsl.exe --distribution $Distro --exec /usr/bin/test -d $ProjectPath
if ($LASTEXITCODE -ne 0) {
    throw "WSL project directory does not exist: $ProjectPath"
}
& wsl.exe --distribution $Distro --exec /usr/bin/test -x $CondaExecutable
if ($LASTEXITCODE -ne 0) {
    throw "WSL Conda executable is missing or not executable: $CondaExecutable"
}
& wsl.exe --distribution $Distro --cd $ProjectPath --exec /usr/bin/test -f `
    "src/backend/desktop_runtime.py"
if ($LASTEXITCODE -ne 0) {
    throw "ResearchMate desktop supervisor is missing from the selected project"
}
& wsl.exe --distribution $Distro --cd $ProjectPath --exec $CondaExecutable run `
    -n $CondaEnvironment python -c "import sys; print(sys.executable)"
if ($LASTEXITCODE -ne 0) {
    throw "Conda environment validation failed: $CondaEnvironment"
}

$installParent = Split-Path -Parent $InstallDirectory
New-Item -ItemType Directory -Force -Path $installParent | Out-Null
$staging = $InstallDirectory + ".installing-" + [Guid]::NewGuid().ToString("N")
$backup = $InstallDirectory + ".previous"
$shortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "ResearchMate.lnk"
$uninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ResearchMate"
$localState = Join-Path $env:LOCALAPPDATA "ResearchMate"
$configPath = Join-Path $localState "desktop-config.json"
$configBackup = Join-Path $env:TEMP ("researchmate-config-" + [Guid]::NewGuid().ToString("N") + ".json")
$shortcutBackup = Join-Path $env:TEMP ("researchmate-shortcut-" + [Guid]::NewGuid().ToString("N") + ".lnk")
$installerDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$switchedInstallation = $false
$shortcutWritten = $false
$registryWritten = $false
$configWritten = $false
$hadConfig = Test-Path -LiteralPath $configPath -PathType Leaf
$hadShortcut = Test-Path -LiteralPath $shortcut -PathType Leaf
$hadRegistry = Test-Path -LiteralPath $uninstallKey
$registrySnapshot = if ($hadRegistry) { Get-ItemProperty -LiteralPath $uninstallKey } else { $null }

try {
    Copy-Item -LiteralPath $PublishedHostDirectory -Destination $staging -Recurse
    Copy-Item -LiteralPath (Join-Path $installerDirectory "Uninstall-ResearchMate.ps1") `
        -Destination (Join-Path $staging "Uninstall-ResearchMate.ps1")
    Copy-Item -LiteralPath (Join-Path $installerDirectory "uninstall-guide-zh-CN.txt") `
        -Destination (Join-Path $staging "uninstall-guide-zh-CN.txt")

    $metadata = [ordered]@{
        schema_version = 1
        installed_at = [DateTimeOffset]::Now.ToString("O")
        distro = $Distro
        project_path = $ProjectPath
        conda_executable = $CondaExecutable
        conda_environment = $CondaEnvironment
        port = $Port
        shortcut_path = $shortcut
        config_path = $configPath
        owned_paths = @($InstallDirectory, $shortcut, $configPath)
        optional_local_state = @($localState)
        external_dependencies = @(
            "WSL distribution: $Distro",
            "ResearchMate checkout: $ProjectPath",
            "Conda executable: $CondaExecutable",
            "Conda environment: $CondaEnvironment"
        )
    }
    $metadata | ConvertTo-Json | Set-Content `
        -LiteralPath (Join-Path $staging "installation-manifest.json") -Encoding UTF8

    if (Test-Path -LiteralPath $backup) {
        Remove-Item -LiteralPath $backup -Recurse -Force
    }
    if (Test-Path -LiteralPath $InstallDirectory) {
        Move-Item -LiteralPath $InstallDirectory -Destination $backup
    }
    Move-Item -LiteralPath $staging -Destination $InstallDirectory
    $switchedInstallation = $true

    if ($hadConfig) {
        Copy-Item -LiteralPath $configPath -Destination $configBackup
    }
    New-Item -ItemType Directory -Force -Path $localState | Out-Null
    $desktopConfig = [ordered]@{
        schema_version = 1
        distro = $Distro
        project_path = $ProjectPath
        conda_executable = $CondaExecutable
        conda_environment = $CondaEnvironment
        port = $Port
    }
    $desktopConfig | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding UTF8
    $configWritten = $true

    $hostExe = Join-Path $InstallDirectory "ResearchMate.WindowsWslHost.exe"

    $shell = New-Object -ComObject WScript.Shell
    if ($hadShortcut) {
        Copy-Item -LiteralPath $shortcut -Destination $shortcutBackup
    }
    $link = $shell.CreateShortcut($shortcut)
    $link.TargetPath = $hostExe
    $link.Arguments = ""
    $link.WorkingDirectory = $InstallDirectory
    $customIcon = Join-Path $localState "shortcut-icon.ico"
    $link.IconLocation = if (Test-Path -LiteralPath $customIcon -PathType Leaf) {
        "$customIcon,0"
    } else {
        "$hostExe,0"
    }
    $link.Description = "ResearchMate Windows + WSL"
    $link.Save()
    $shortcutWritten = $true

    New-Item -Path $uninstallKey -Force | Out-Null
    $registryWritten = $true
    $uninstallScript = Join-Path $InstallDirectory "Uninstall-ResearchMate.ps1"
    $uninstallCommand = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' +
        $uninstallScript + '"'
    Set-ItemProperty -Path $uninstallKey -Name DisplayName -Value "ResearchMate (Windows + WSL)"
    Set-ItemProperty -Path $uninstallKey -Name DisplayVersion -Value "0.1.0-prototype"
    Set-ItemProperty -Path $uninstallKey -Name Publisher -Value "ResearchMate"
    Set-ItemProperty -Path $uninstallKey -Name InstallLocation -Value $InstallDirectory
    Set-ItemProperty -Path $uninstallKey -Name DisplayIcon -Value $hostExe
    Set-ItemProperty -Path $uninstallKey -Name UninstallString -Value $uninstallCommand
    Set-ItemProperty -Path $uninstallKey -Name NoModify -Value 1 -Type DWord
    Set-ItemProperty -Path $uninstallKey -Name NoRepair -Value 1 -Type DWord

    if (Test-Path -LiteralPath $backup) {
        Remove-Item -LiteralPath $backup -Recurse -Force
    }
    if (Test-Path -LiteralPath $configBackup) {
        Remove-Item -LiteralPath $configBackup -Force
    }
    if (Test-Path -LiteralPath $shortcutBackup) {
        Remove-Item -LiteralPath $shortcutBackup -Force
    }
    Write-Output "Installed ResearchMate: $InstallDirectory"
    Write-Output "Desktop shortcut: $shortcut"
}
catch {
    if ($registryWritten -and (Test-Path -LiteralPath $uninstallKey)) {
        Remove-Item -LiteralPath $uninstallKey -Recurse -Force
    }
    if ($hadRegistry -and $registrySnapshot) {
        New-Item -Path $uninstallKey -Force | Out-Null
        foreach ($name in @("DisplayName", "DisplayVersion", "Publisher", "InstallLocation",
                            "DisplayIcon", "UninstallString")) {
            if ($null -ne $registrySnapshot.$name) {
                Set-ItemProperty -Path $uninstallKey -Name $name -Value $registrySnapshot.$name
            }
        }
        foreach ($name in @("NoModify", "NoRepair")) {
            if ($null -ne $registrySnapshot.$name) {
                Set-ItemProperty -Path $uninstallKey -Name $name `
                    -Value ([int]$registrySnapshot.$name) -Type DWord
            }
        }
    }
    if ($shortcutWritten -and (Test-Path -LiteralPath $shortcut -PathType Leaf)) {
        Remove-Item -LiteralPath $shortcut -Force
    }
    if ($hadShortcut -and (Test-Path -LiteralPath $shortcutBackup -PathType Leaf)) {
        Copy-Item -LiteralPath $shortcutBackup -Destination $shortcut
    }
    if ($configWritten) {
        if ($hadConfig -and (Test-Path -LiteralPath $configBackup -PathType Leaf)) {
            Copy-Item -LiteralPath $configBackup -Destination $configPath -Force
        }
        elseif (Test-Path -LiteralPath $configPath -PathType Leaf) {
            Remove-Item -LiteralPath $configPath -Force
        }
    }
    if (Test-Path -LiteralPath $configBackup -PathType Leaf) {
        Remove-Item -LiteralPath $configBackup -Force
    }
    if (Test-Path -LiteralPath $shortcutBackup -PathType Leaf) {
        Remove-Item -LiteralPath $shortcutBackup -Force
    }
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
    if ($switchedInstallation -and (Test-Path -LiteralPath $InstallDirectory)) {
        Remove-Item -LiteralPath $InstallDirectory -Recurse -Force
    }
    if (Test-Path -LiteralPath $backup) {
        if (-not (Test-Path -LiteralPath $InstallDirectory)) {
            Move-Item -LiteralPath $backup -Destination $InstallDirectory
        }
    }
    throw
}
