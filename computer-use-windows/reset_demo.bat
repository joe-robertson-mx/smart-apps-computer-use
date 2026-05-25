@echo off
REM ---------------------------------------------------------------------------
REM Reset the demo to its starting state WITHOUT relaunching.
REM Stops the components and deletes the submitted records so the next run
REM starts clean. (start_demo_env.bat also does this automatically.)
REM ---------------------------------------------------------------------------
cd /d "%~dp0"
call stop_demo_env.bat
echo Clearing submitted records...
if exist "data\warranty_cases.json" del /q "data\warranty_cases.json"
if exist "data\dispatch_records.json" del /q "data\dispatch_records.json"
echo Demo reset to starting state.
