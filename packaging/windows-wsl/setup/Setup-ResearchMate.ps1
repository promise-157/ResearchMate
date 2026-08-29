param(
    [ValidateSet("Check", "Plan", "Apply", "Install")][string]$Mode = "Check",
    [string]$ConfigPath = "",
    [string]$PlanPath = "",
    [string]$Distro = "",
    [string]$ProjectPath = "",
    [string]$CondaExecutable = "",
    [string]$CondaEnvironment = "researchmate",
    [int]$Port = 8000,
    [string]$InstallDirectory = "",
    [string]$PublishedHostDirectory = "",
    [string]$DotNetExecutable = "dotnet",
    [switch]$NonInteractive,
    [switch]$Yes
)

$ErrorActionPreference = "Stop"
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$windowsWslDirectory = Split-Path -Parent $scriptDirectory
$repositoryDirectory = (Resolve-Path (Join-Path $scriptDirectory "..\..\..")).Path
$installerDirectory = Join-Path $windowsWslDirectory "installer"
if (-not $PlanPath) {
    $PlanPath = Join-Path $repositoryDirectory "researchmate-install-plan.json"
}
$approvedPlan = $null
if ($Mode -eq "Apply") {
    if (-not (Test-Path -LiteralPath $PlanPath -PathType Leaf)) {
        throw "Install plan not found. Run Plan, review the JSON, then run Apply."
    }
    $approvedPlan = Get-Content -LiteralPath $PlanPath -Raw | ConvertFrom-Json
    if ($approvedPlan.schema_version -ne 1) { throw "Unsupported install plan version" }
    $Distro = [string]$approvedPlan.distro
    $ProjectPath = [string]$approvedPlan.project_path
    $CondaExecutable = [string]$approvedPlan.conda_executable
    $CondaEnvironment = [string]$approvedPlan.conda_environment
    $Port = [int]$approvedPlan.port
    $InstallDirectory = [string]$approvedPlan.install_directory
    $PublishedHostDirectory = [string]$approvedPlan.published_host_directory
    $DotNetExecutable = [string]$approvedPlan.dotnet_executable
}

function Add-Check([System.Collections.ArrayList]$Checks, [string]$Name, [bool]$Ok,
                   [bool]$Required, [string]$Detail, [string]$Remedy) {
    [void]$Checks.Add([ordered]@{
        name = $Name
        ok = $Ok
        required = $Required
        detail = $Detail
        remedy = $(if ($Ok) { "" } else { $Remedy })
    })
}

function Invoke-Wsl([string[]]$Arguments) {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & wsl.exe @Arguments 2>&1
        $exitCode = $LASTEXITCODE
        return [ordered]@{ exit_code = $exitCode; output = ($output -join "`n").Trim() }
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
}

function Import-InstallConfig([string]$Path) {
    if (-not $Path) { throw "Install mode requires -ConfigPath" }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Install config not found: $Path"
    }
    $config = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    $allowed = @(
        "schema_version", "distro", "project_path", "conda_executable",
        "conda_environment", "port", "install_directory",
        "published_host_directory", "dotnet_executable"
    )
    foreach ($property in $config.PSObject.Properties.Name) {
        if ($allowed -notcontains $property) { throw "Unknown install config field: $property" }
    }
    if ([int]$config.schema_version -ne 1) { throw "Unsupported install config version" }
    foreach ($required in @("distro", "project_path", "conda_executable")) {
        if (-not [string]$config.$required) { throw "Install config field is required: $required" }
    }
    return $config
}

function Resolve-RepositoryDefaults {
    $resolvedDistro = $Distro
    $resolvedProject = $ProjectPath
    if ($repositoryDirectory -match '^\\\\wsl(?:\.localhost|\$)\\([^\\]+)\\(.*)$') {
        if (-not $resolvedDistro) { $resolvedDistro = $Matches[1] }
        if (-not $resolvedProject) { $resolvedProject = "/" + ($Matches[2] -replace '\\', '/') }
    }
    return @($resolvedDistro, $resolvedProject)
}

function Resolve-Conda([string]$SelectedDistro) {
    if ($CondaExecutable) { return $CondaExecutable }
    if (-not $SelectedDistro) { return "" }
    $probe = Invoke-Wsl @(
        "--distribution", $SelectedDistro, "--exec", "/bin/sh", "-lc",
        'for p in "$HOME/miniconda3/condabin/conda" "$HOME/anaconda3/condabin/conda" "$HOME/mambaforge/condabin/conda" "$HOME/miniforge3/condabin/conda"; do [ -x "$p" ] && { printf "%s" "$p"; exit 0; }; done; command -v conda 2>/dev/null'
    )
    if ($probe.exit_code -eq 0) { return [string]$probe.output }
    return ""
}

function Get-Checks([string]$SelectedDistro, [string]$SelectedProject,
                    [string]$SelectedConda) {
    $checks = New-Object System.Collections.ArrayList
    Add-Check $checks "wsl.exe" ([bool](Get-Command wsl.exe -ErrorAction SilentlyContinue)) $true `
        "Windows Subsystem for Linux command" `
        "Install WSL 2 from an elevated PowerShell: wsl --install"

    $distros = @()
    if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
        $rawDistros = & wsl.exe --list --quiet 2>$null
        $distros = @($rawDistros | ForEach-Object { ($_ -replace "`0", "").Trim() } | Where-Object { $_ })
    }
    Add-Check $checks "WSL distribution" ($SelectedDistro -and $distros -contains $SelectedDistro) $true `
        $(if ($SelectedDistro) { $SelectedDistro } else { "not selected" }) `
        "Choose an installed distribution shown by: wsl --list --verbose"

    $projectOk = $false
    if ($SelectedDistro -and $SelectedProject) {
        $probe = Invoke-Wsl @("--distribution", $SelectedDistro, "--exec", "/usr/bin/test", "-f",
            "$SelectedProject/src/backend/desktop_runtime.py")
        $projectOk = $probe.exit_code -eq 0
    }
    Add-Check $checks "ResearchMate checkout" $projectOk $true `
        $(if ($SelectedProject) { $SelectedProject } else { "not selected" }) `
        "Clone the repository inside the WSL Linux filesystem and select its absolute path"

    $condaOk = $false
    if ($SelectedDistro -and $SelectedConda) {
        $probe = Invoke-Wsl @("--distribution", $SelectedDistro, "--exec", "/usr/bin/test", "-x", $SelectedConda)
        $condaOk = $probe.exit_code -eq 0
    }
    Add-Check $checks "Conda-compatible executable" $condaOk $true `
        $(if ($SelectedConda) { $SelectedConda } else { "not selected" }) `
        "Install Conda, Mamba or Micromamba yourself, then provide its WSL absolute path"

    $pythonOk = $false
    $backendPackagesOk = $false
    if ($condaOk) {
        $probe = Invoke-Wsl @("--distribution", $SelectedDistro, "--exec", $SelectedConda,
            "run", "-n", $CondaEnvironment, "python", "-c",
            "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)")
        $pythonOk = $probe.exit_code -eq 0
        if ($pythonOk) {
            $probe = Invoke-Wsl @("--distribution", $SelectedDistro, "--exec", $SelectedConda,
                "run", "-n", $CondaEnvironment, "python", "-c",
                "import fastapi,uvicorn,httpx,bs4,lxml,apscheduler,yaml,pydantic,multipart,PIL")
            $backendPackagesOk = $probe.exit_code -eq 0
        }
    }
    Add-Check $checks "Python 3.11 environment" $pythonOk $true $CondaEnvironment `
        "Create it yourself, for example: conda create -n $CondaEnvironment python=3.11"
    Add-Check $checks "Backend Python packages" $backendPackagesOk $true `
        "src/backend/requirements.txt" `
        "In WSL run: pip install -r src/backend/requirements.txt"

    $nodeOk = $false
    $npmOk = $false
    $frontendInstalled = $false
    $frontendBuilt = $false
    if ($condaOk) {
        $nodeProbe = Invoke-Wsl @("--distribution", $SelectedDistro, "--exec", $SelectedConda,
            "run", "-n", $CondaEnvironment, "node", "--version")
        $npmProbe = Invoke-Wsl @("--distribution", $SelectedDistro, "--exec", $SelectedConda,
            "run", "-n", $CondaEnvironment, "npm", "--version")
        $nodeOk = $nodeProbe.exit_code -eq 0
        $npmOk = $npmProbe.exit_code -eq 0
        if ($SelectedProject) {
            $moduleProbe = Invoke-Wsl @("--distribution", $SelectedDistro, "--exec", "/usr/bin/test", "-d",
                "$SelectedProject/src/frontend/node_modules/vue")
            $frontendInstalled = $moduleProbe.exit_code -eq 0
            $buildProbe = Invoke-Wsl @("--distribution", $SelectedDistro, "--exec", "/usr/bin/test", "-f",
                "$SelectedProject/src/frontend/dist/index.html")
            $frontendBuilt = $buildProbe.exit_code -eq 0
        }
    }
    Add-Check $checks "Node.js (build only)" ($frontendBuilt -or $nodeOk) $true `
        $(if ($frontendBuilt) { "frontend production build already exists" } else { "required to build Vue frontend" }) `
        "Install a supported Node.js release where the selected Conda environment can find it; Vue itself is installed by npm"
    Add-Check $checks "npm (build only)" ($frontendBuilt -or $npmOk) $true "frontend package manager" `
        "Install npm inside WSL with your chosen Node.js distribution"
    Add-Check $checks "Vue/frontend packages (build only)" ($frontendBuilt -or $frontendInstalled) $true `
        $(if ($frontendBuilt) { "frontend production build already exists" } else { "src/frontend/node_modules" }) `
        "In WSL run: cd src/frontend && npm ci"
    Add-Check $checks "Frontend production build" $frontendBuilt $true "src/frontend/dist/index.html" `
        "In WSL run: cd src/frontend && npm run build"

    $webViewOk = [bool](Get-ItemProperty `
        "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" `
        -ErrorAction SilentlyContinue)
    if (-not $webViewOk) {
        $webViewOk = [bool](Get-ItemProperty `
            "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" `
            -ErrorAction SilentlyContinue)
    }
    Add-Check $checks "WebView2 Runtime" $webViewOk $true "Windows embedded browser runtime" `
        "Install Microsoft Edge WebView2 Evergreen Runtime from Microsoft"

    $publishedExe = if ($PublishedHostDirectory) {
        Join-Path $PublishedHostDirectory "ResearchMate.WindowsWslHost.exe"
    } else { "" }
    $publishedOk = $publishedExe -and (Test-Path -LiteralPath $publishedExe -PathType Leaf)
    if ($publishedOk) {
        $publishedTimestamp = (Get-Item -LiteralPath $publishedExe).LastWriteTimeUtc
        $newerSource = Get-ChildItem -LiteralPath (Join-Path $windowsWslDirectory "host") -File |
            Where-Object { $_.Extension -in ".cs", ".csproj" -and $_.LastWriteTimeUtc -gt $publishedTimestamp } |
            Select-Object -First 1
        if ($newerSource) { $publishedOk = $false }
    }
    $dotnetOk = [bool](Get-Command $DotNetExecutable -ErrorAction SilentlyContinue)
    Add-Check $checks ".NET SDK (build only)" ($publishedOk -or $dotnetOk) $true `
        $(if ($publishedOk) { "prebuilt self-contained host selected" } else { "needed to build host from Git" }) `
        "Install .NET 10 SDK yourself or select a trusted prebuilt ResearchMate host"

    $tesseractOk = $false
    if ($SelectedDistro) {
        $probe = if ($condaOk) {
            Invoke-Wsl @("--distribution", $SelectedDistro, "--exec", $SelectedConda,
                "run", "-n", $CondaEnvironment, "tesseract", "--version")
        } else {
            Invoke-Wsl @("--distribution", $SelectedDistro, "--exec", "/usr/bin/env", "tesseract", "--version")
        }
        $tesseractOk = $probe.exit_code -eq 0
    }
    Add-Check $checks "Tesseract OCR" $tesseractOk $false "optional image OCR feature" `
        "Install Tesseract and the language packs you need inside WSL, or leave OCR unavailable"
    return $checks
}

function Show-Checks($Checks) {
    foreach ($check in $Checks) {
        $mark = if ($check.ok) { "OK" } elseif ($check.required) { "MISSING" } else { "OPTIONAL" }
        Write-Output ("[{0}] {1}: {2}" -f $mark, $check.name, $check.detail)
        if ($check.remedy) { Write-Output ("  Remedy: " + $check.remedy) }
    }
}

if ($Mode -eq "Install") {
    $installConfig = Import-InstallConfig $ConfigPath
    $Distro = [string]$installConfig.distro
    $ProjectPath = [string]$installConfig.project_path
    $CondaExecutable = [string]$installConfig.conda_executable
    if ($installConfig.conda_environment) { $CondaEnvironment = [string]$installConfig.conda_environment }
    if ($installConfig.port) { $Port = [int]$installConfig.port }
    if ($installConfig.install_directory) { $InstallDirectory = [string]$installConfig.install_directory }
    if ($installConfig.published_host_directory) { $PublishedHostDirectory = [string]$installConfig.published_host_directory }
    if ($installConfig.dotnet_executable) { $DotNetExecutable = [string]$installConfig.dotnet_executable }
    $NonInteractive = $true
}

$defaults = Resolve-RepositoryDefaults
$selectedDistro = [string]$defaults[0]
$selectedProject = [string]$defaults[1]
if (-not $selectedDistro -and -not $NonInteractive) {
    $selectedDistro = Read-Host "WSL distribution name"
}
if (-not $selectedProject -and -not $NonInteractive) {
    $selectedProject = Read-Host "ResearchMate absolute path inside WSL"
}
$selectedConda = Resolve-Conda $selectedDistro
if (-not $selectedConda -and -not $NonInteractive) {
    $selectedConda = Read-Host "Conda/Mamba executable absolute path inside WSL"
}
if (-not $InstallDirectory) {
    $InstallDirectory = if (Test-Path -LiteralPath "D:\Apps" -PathType Container) {
        "D:\Apps\ResearchMate"
    } else {
        Join-Path $env:LOCALAPPDATA "Programs\ResearchMate"
    }
}
if (-not $PublishedHostDirectory) {
    $PublishedHostDirectory = Join-Path $windowsWslDirectory "artifacts\win-x64"
}
$checks = Get-Checks $selectedDistro $selectedProject $selectedConda
Show-Checks $checks
$requiredFailures = @($checks | Where-Object { $_.required -and -not $_.ok })
if ($Mode -eq "Check") {
    if ($requiredFailures.Count) { exit 2 }
    exit 0
}

$plan = [ordered]@{
    schema_version = 1
    generated_at = [DateTimeOffset]::Now.ToString("O")
    distro = $selectedDistro
    project_path = $selectedProject
    conda_executable = $selectedConda
    conda_environment = $CondaEnvironment
    port = $Port
    install_directory = $InstallDirectory
    published_host_directory = $PublishedHostDirectory
    dotnet_executable = $DotNetExecutable
    actions = @(
        "Build or reuse the self-contained Windows x64 host",
        "Create or replace the selected ResearchMate Windows install directory",
        "Write desktop-config.json under LocalAppData",
        "Create one ResearchMate desktop shortcut",
        "Register a current-user uninstall entry"
    )
    external_dependencies_not_owned = @(
        "WSL and the selected Linux distribution",
        "Git and the ResearchMate checkout",
        "Node.js, npm and frontend packages",
        ".NET SDK used to build from Git",
        "Conda/Mamba/Micromamba and the selected Python environment",
        "Tesseract and language packs",
        "ResearchMate workspaces, assets, archives and keys"
    )
    checks = $checks
}

if ($Mode -eq "Plan" -or $Mode -eq "Install") {
    $plan | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $PlanPath -Encoding UTF8
    Write-Output "Plan written: $PlanPath"
    if ($requiredFailures.Count) { exit 2 }
    if ($Mode -eq "Plan") { exit 0 }
    Write-Output "Planned installation:"
    $plan | ConvertTo-Json -Depth 8 | Write-Output
    if (-not $Yes) {
        $answer = Read-Host "Apply this plan now? Type YES to continue"
        if ($answer -cne "YES") {
            Write-Output "Cancelled; the plan was kept and no installation changes were applied."
            exit 0
        }
    }
    $approvedPlan = $plan
}

if ($requiredFailures.Count) { throw "Required checks failed; no changes were applied" }
$approved = $approvedPlan

$publishedExe = Join-Path ([string]$approved.published_host_directory) "ResearchMate.WindowsWslHost.exe"
$publishedCurrent = Test-Path -LiteralPath $publishedExe -PathType Leaf
if ($publishedCurrent) {
    $publishedTimestamp = (Get-Item -LiteralPath $publishedExe).LastWriteTimeUtc
    $newerSource = Get-ChildItem -LiteralPath (Join-Path $windowsWslDirectory "host") -File |
        Where-Object { $_.Extension -in ".cs", ".csproj" -and $_.LastWriteTimeUtc -gt $publishedTimestamp } |
        Select-Object -First 1
    if ($newerSource) { $publishedCurrent = $false }
}
if (-not $publishedCurrent) {
    & (Join-Path $installerDirectory "Build-ResearchMateHost.ps1") `
        -DotNetExecutable ([string]$approved.dotnet_executable) `
        -OutputDirectory ([string]$approved.published_host_directory)
    if ($LASTEXITCODE -ne 0) { throw "Windows host build failed" }
}
& (Join-Path $installerDirectory "Install-ResearchMate.ps1") `
    -Distro ([string]$approved.distro) `
    -ProjectPath ([string]$approved.project_path) `
    -CondaExecutable ([string]$approved.conda_executable) `
    -CondaEnvironment ([string]$approved.conda_environment) `
    -Port ([int]$approved.port) `
    -PublishedHostDirectory ([string]$approved.published_host_directory) `
    -InstallDirectory ([string]$approved.install_directory)
if ($LASTEXITCODE -ne 0) { throw "ResearchMate installation failed" }
