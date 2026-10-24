<#
.SYNOPSIS
    Personal Agentic Fleet — Self-Bootstrapping Python (>=3.10) & Security Provisioner for Windows.
.DESCRIPTION
    1. Discovers an existing Python >= 3.10 interpreter (checks .venv, py launcher, C:\Python3*, AppData, PATH).
    2. If Python >= 3.10 is missing, automatically installs Python 3.12 in User Scope (no Admin UAC required).
    3. Hardens NTFS ACL permissions on fleet/data/user/ so only the current Windows user can access the vault.
    4. Creates fleet.yaml from fleet.yaml.example if missing.
    5. Installs automated Git pre-commit and pre-push security hooks.
    6. Runs Fleet Doctor & 12-Layer Security Scanner (--strict).
    7. Optionally launches Fleet Server & Daemon silently in the background (-Launch).
#>
param(
    [switch]$Launch = $false,
    [switch]$CreateVenv = $false
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "  Personal Agentic Fleet — Bootstrap & Security Provisioner" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

function Test-PythonVersion310Plus([string]$PythonExe) {
    if (-not $PythonExe -or -not (Test-Path $PythonExe -ErrorAction SilentlyContinue)) {
        return $false
    }
    try {
        $verOut = & $PythonExe -c "import sys; print(1 if sys.version_info >= (3, 10) else 0)" 2>$null
        return ($verOut -and $verOut.Trim() -eq "1")
    } catch {
        return $false
    }
}

function Find-ValidPython {
    # 1. Check local virtual environment first
    $venvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (Test-PythonVersion310Plus $venvPy) { return $venvPy }

    # 2. Check standard C:\Python3* and User AppData Python installations (newest first)
    $candidates = @()
    $candidates += Get-ChildItem -Path "C:\Python3*\python.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -ExpandProperty FullName
    $candidates += Get-ChildItem -Path "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -ExpandProperty FullName

    # 3. Check PATH python
    $pathPy = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($pathPy) { $candidates += $pathPy }

    foreach ($cand in $candidates) {
        if (Test-PythonVersion310Plus $cand) {
            return $cand
        }
    }
    return $null
}

$PythonExe = Find-ValidPython

if (-not $PythonExe) {
    Write-Host "[!] Python >= 3.10 not found. Auto-provisioning Python 3.12 (User Scope)..." -ForegroundColor Yellow
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
    } else {
        $installerUrl = "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
        $installerPath = Join-Path $env:TEMP "python-3.12-installer.exe"
        Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
        Start-Process -FilePath $installerPath -ArgumentList "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_test=0" -Wait
    }
    $PythonExe = Find-ValidPython
    if (-not $PythonExe) {
        Write-Error "Failed to locate or provision Python >= 3.10. Please install Python 3.10+ from https://www.python.org/downloads/"
        exit 1
    }
}

$PyVer = (& $PythonExe -c "import sys; print(sys.version.split()[0])").Trim()
Write-Host "[OK] Verified Python Interpreter: $PythonExe (v$PyVer >= 3.10)" -ForegroundColor Green

# Optional Virtual Environment Creation
if ($CreateVenv -and -not (Test-Path (Join-Path $RepoRoot ".venv\Scripts\python.exe"))) {
    Write-Host "[*] Creating isolated .venv virtual environment..." -ForegroundColor Cyan
    & $PythonExe -m venv (Join-Path $RepoRoot ".venv")
    $PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
}

# Initialize fleet.yaml from template if missing
$ConfigYaml = Join-Path $RepoRoot "fleet.yaml"
$TemplateYaml = Join-Path $RepoRoot "fleet.yaml.example"
if (-not (Test-Path $ConfigYaml) -and (Test-Path $TemplateYaml)) {
    Copy-Item $TemplateYaml $ConfigYaml
    Write-Host "[OK] Created local fleet.yaml from fleet.yaml.example" -ForegroundColor Green
}

# Harden fleet/data/user/ NTFS ACLs (Current User Only)
$UserVault = Join-Path $RepoRoot "fleet\data\user"
if (-not (Test-Path $UserVault)) {
    New-Item -ItemType Directory -Path $UserVault -Force | Out-Null
}
try {
    & icacls $UserVault /inheritance:r /grant:r "$($env:USERNAME):(OI)(CI)F" /grant:r "SYSTEM:(OI)(CI)F" /grant:r "Administrators:(OI)(CI)F" >$null 2>&1
    Write-Host "[OK] Hardened NTFS ACLs on fleet/data/user/ (Restricted to $env:USERNAME)" -ForegroundColor Green
} catch {
    Write-Host "[i] Note: Standard ACL applied to fleet/data/user/" -ForegroundColor Gray
}

# Install Git Pre-Commit & Pre-Push Security Hooks
$env:PYTHONPATH = $RepoRoot
& $PythonExe -m fleet.tools.install_git_hooks

# Run Fleet Doctor & 12-Layer Security Audit
& $PythonExe -m fleet.tools.fleet_doctor --strict
if ($LASTEXITCODE -ne 0) {
    Write-Error "Fleet Doctor / Security Audit reported critical issues. Aborting."
    exit $LASTEXITCODE
}

if ($Launch) {
    $PythonwExe = Join-Path (Split-Path $PythonExe -Parent) "pythonw.exe"
    if (-not (Test-Path $PythonwExe)) { $PythonwExe = $PythonExe }
    Start-Process -FilePath $PythonwExe -ArgumentList "-m", "fleet.server" -WorkingDirectory $RepoRoot -WindowStyle Hidden
    Start-Process -FilePath $PythonwExe -ArgumentList "-m", "fleet.daemon" -WorkingDirectory $RepoRoot -WindowStyle Hidden
    Write-Host "[OK] Fleet Server & Daemon launched silently at http://127.0.0.1:7890" -ForegroundColor Green
}
