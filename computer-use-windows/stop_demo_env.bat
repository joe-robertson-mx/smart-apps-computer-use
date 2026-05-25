@echo off
REM ---------------------------------------------------------------------------
REM Stop the BOAT 2026 demo components.
REM Targets ONLY the python processes whose command line references this demo's
REM scripts - it will not touch Mendix, other python apps, or the browser.
REM ---------------------------------------------------------------------------
cd /d "%~dp0"
echo Stopping demo components...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { ($_.Name -match '^pythonw?\.exe$') -and ($_.CommandLine -match 'windows_server\.py|warranty_case_manager\.py|returns_portal[\\/]app\.py') } | ForEach-Object { Write-Host ('  stopping PID ' + $_.ProcessId + '  (' + $_.Name + ')'); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo Done.
