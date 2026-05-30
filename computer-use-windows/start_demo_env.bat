@echo off
REM ---------------------------------------------------------------------------
REM BOAT 2026 computer-use demo - Windows environment launcher.
REM Every run is a CLEAN RESTART: any previous instances are stopped and the
REM submitted records are cleared before the components start again.
REM Run this from the computer-use-windows folder.
REM ---------------------------------------------------------------------------
cd /d "%~dp0"

echo === Clean restart: stopping any previous demo components ===
call stop_demo_env.bat

echo === Clearing submitted records (starting state) ===
if exist "data\warranty_cases.json" del /q "data\warranty_cases.json"
if exist "data\dispatch_records.json" del /q "data\dispatch_records.json"

echo === Starting demo environment ===

REM Start the legacy web portal (Flask) on port 5050.
REM Run app.py directly - simpler and more robust than the flask CLI here.
start "Returns Portal" pythonw returns_portal\app.py

REM Start the legacy desktop app (launches minimised to the taskbar).
start "Warranty Manager" pythonw warranty_case_manager.py

REM Give the portal a moment to come up, then open it in the browser.
timeout /t 2 /nobreak >nul
start msedge http://localhost:5050

REM Start the computer-use server windowless (pythonw, no console) so a stray
REM agent keystroke/click can never focus, Ctrl+C, or close it. It writes its own
REM log to C:\cu_server.log.
timeout /t 1 /nobreak >nul
echo Starting Windows computer use server (port 8081, or COMPUTER_USE_PORT if set)...
start "" pythonw windows_server.py
