# Personal Agentic Fleet - Windows Auto-Start Manager
param (
    [string]$Action = "enable"
)

$startupFolder = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupFolder 'FleetControlCenter.lnk'
$scriptDir = $PSScriptRoot
$vbsLauncher = Join-Path $scriptDir 'start_control_center.vbs'

if ($Action -eq "enable") {
    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host "  Configuring Personal Agentic Fleet Windows Auto-Start   " -ForegroundColor Cyan
    Write-Host "==========================================================" -ForegroundColor Cyan
    
    if (-not (Test-Path $vbsLauncher)) {
        Write-Host "ERROR: Launcher '$vbsLauncher' not found." -ForegroundColor Red
        exit 1
    }

    try {
        $wsh = New-Object -ComObject WScript.Shell
        $shortcut = $wsh.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = "wscript.exe"
        $shortcut.Arguments = "`"$vbsLauncher`""
        $shortcut.WorkingDirectory = $scriptDir
        $shortcut.Description = "Personal Agentic Fleet Control Center"
        $shortcut.Save()

        Write-Host ""
        Write-Host "  [SUCCESS] Auto-start configured successfully!" -ForegroundColor Green
        Write-Host "  Startup Shortcut : $shortcutPath" -ForegroundColor White
        Write-Host "  Target Launcher  : $vbsLauncher" -ForegroundColor White
        Write-Host "  Working Directory: $scriptDir" -ForegroundColor White
        Write-Host ""
        Write-Host "When your laptop boots, the Control Center will now" -ForegroundColor Green
        Write-Host "automatically launch in the background at http://127.0.0.1:7890." -ForegroundColor Green
        Write-Host "==========================================================" -ForegroundColor Cyan
    } catch {
        Write-Host "Failed to create shortcut: $_" -ForegroundColor Red
        exit 1
    }
}
elseif ($Action -eq "disable") {
    Write-Host "==========================================================" -ForegroundColor Yellow
    Write-Host "  Disabling Personal Agentic Fleet Windows Auto-Start     " -ForegroundColor Yellow
    Write-Host "==========================================================" -ForegroundColor Yellow

    if (Test-Path $shortcutPath) {
        Remove-Item $shortcutPath -Force
        Write-Host ""
        Write-Host "  [SUCCESS] Auto-start shortcut removed:" -ForegroundColor Green
        Write-Host "  $shortcutPath" -ForegroundColor White
        Write-Host ""
        Write-Host "Personal Agentic Fleet will no longer start on boot." -ForegroundColor Yellow
    } else {
        Write-Host ""
        Write-Host "  [INFO] Auto-start was already disabled (no shortcut found)." -ForegroundColor White
    }
    Write-Host "==========================================================" -ForegroundColor Yellow
}
elseif ($Action -eq "status") {
    if (Test-Path $shortcutPath) {
        Write-Host "Personal Agentic Fleet Auto-Start: ENABLED ($shortcutPath)" -ForegroundColor Green
    } else {
        Write-Host "Personal Agentic Fleet Auto-Start: DISABLED" -ForegroundColor Yellow
    }
}
