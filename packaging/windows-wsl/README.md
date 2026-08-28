# Windows + WSL desktop host

This directory contains the source-backed Windows + WSL desktop delivery described in
`docs/PLATFORM_DISTRIBUTION.md`. The host is self-contained; the current installer still expects an existing
ResearchMate checkout and Conda environment inside WSL.

The host normally reads the explicit configuration confirmed by the setup guide from
`%LOCALAPPDATA%\ResearchMate\desktop-config.json`. A developer may instead supply a specific config file:

```powershell
ResearchMate.WindowsWslHost.exe `
  --config C:\path\to\desktop-config.json
```

The transparent setup guide discovers candidates, validates and persists the user's chosen distribution, project
path and Conda-compatible executable. The explicit executable path is required because a non-interactive WSL
process does not necessarily load the PATH used by the user's terminal.
The host starts the existing production
backend through a private WSL supervisor, waits for `/api/health`, and embeds the existing Vue application in
WebView2. Closing the only window requests graceful shutdown of the exact owned backend process group.

Do not use `--kill`, `wsl --shutdown`, or an unauthenticated HTTP shutdown route as part of this lifecycle.

## Check, plan and install

Start with the setup guide described in the repository README. `Check` is read-only, `Plan` writes an auditable
JSON file, and `Apply` rechecks and uses exactly that approved plan. It never installs or removes WSL, Git, .NET,
Node, Conda-compatible tools, Python, Tesseract, source or user data.

Publish the self-contained Windows x64 host:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  packaging/windows-wsl/installer/Build-ResearchMateHost.ps1
```

The low-level installer remains available for development after replacing the values with validated local paths:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  packaging/windows-wsl/installer/Install-ResearchMate.ps1 `
  -Distro Ubuntu `
  -ProjectPath /home/alice/ResearchMate `
  -CondaExecutable /home/alice/miniforge3/condabin/conda `
  -PublishedHostDirectory packaging/windows-wsl/artifacts/win-x64
```

The default target is `D:\Apps\ResearchMate` when `D:\Apps` exists, otherwise
`%LOCALAPPDATA%\Programs\ResearchMate`. Installation validates WSL, the checkout, the supervisor and Conda
environment before switching directories. It creates one desktop shortcut and a current-user uninstall entry.
The shortcut contains no personal WSL arguments; the host reads the separate desktop config. Re-running the
installer performs a staged replacement with rollback of both host and config on failure.

Close the ResearchMate window before uninstalling. Use Windows Installed Apps or run the installed
`Uninstall-ResearchMate.ps1`; pass `-RemoveLocalState` only to also remove Windows-side logs and WebView state.
The uninstaller never removes WSL, Conda, source, workspaces, assets or archives. The installed Chinese text file
`uninstall-guide-zh-CN.txt` lists the exact boundaries.

## Development verification

Build artifacts remain ignored. Restore is only needed when the locked package is absent from the configured
NuGet cache.

```powershell
dotnet restore packaging/windows-wsl/host-tests/ResearchMate.WindowsWslHost.Tests.csproj
dotnet build packaging/windows-wsl/host/ResearchMate.WindowsWslHost.csproj -c Release --no-restore
dotnet build packaging/windows-wsl/host-tests/ResearchMate.WindowsWslHost.Tests.csproj -c Debug --no-restore
dotnet packaging/windows-wsl/host-tests/bin/Debug/net10.0-windows/ResearchMate.WindowsWslHost.Tests.dll
```

The real probes require the explicit local WSL values and still use only disposable `/tmp` fixtures:

```powershell
dotnet packaging/windows-wsl/host-tests/bin/Debug/net10.0-windows/ResearchMate.WindowsWslHost.Tests.dll `
  --real-wsl Ubuntu /home/alice/ResearchMate /home/alice/miniforge3/condabin/conda

dotnet packaging/windows-wsl/host-tests/bin/Debug/net10.0-windows/ResearchMate.WindowsWslHost.Tests.dll `
  --real-host Ubuntu /home/alice/ResearchMate /home/alice/miniforge3/condabin/conda
```

Those values are examples for the current development machine, not portable defaults.
