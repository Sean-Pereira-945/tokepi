@echo off
rem Start the full DriftGuard live demo: server, dashboard, and demo script.
rem Uses a local SQLite file (driftguard-local.db), never the database in .env.
rem Guide: docs\demo.md

setlocal
cd /d "%~dp0"

set "DEMO_EMAIL=demo@driftguard.local"
set "DEMO_PASSWORD=driftguard-demo"
set "DEMO_PORT=8000"
set "DEMO_URL=http://127.0.0.1:%DEMO_PORT%"
set "DATABASE_URL=sqlite:///./driftguard-local.db"
set "PYTHONUTF8=1"

rem --- 1. Python environment -----------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo Creating the Python environment ^(first run only^)...
    python -m venv .venv || goto :fail
    ".venv\Scripts\python.exe" -m pip install -e ".[server]" || goto :fail
)

rem --- 2. Dashboard build --------------------------------------------------
if not exist "driftguard\server\static\index.html" (
    echo Building the dashboard ^(first run only^)...
    pushd frontend
    call npm ci || (popd & goto :fail)
    call npm run build || (popd & goto :fail)
    popd
)

rem --- 3. Server -----------------------------------------------------------
curl -s -o nul "%DEMO_URL%/health"
if errorlevel 1 (
    echo Starting the DriftGuard server in a new window...
    start "DriftGuard server" ".venv\Scripts\driftguard-server.exe" --port %DEMO_PORT%
) else (
    echo A DriftGuard server is already running on port %DEMO_PORT%.
)

echo Waiting for the server...
set /a TRIES=0
:wait
curl -s -o nul "%DEMO_URL%/health"
if not errorlevel 1 goto :ready
set /a TRIES+=1
if %TRIES% geq 30 (
    echo The server did not start. Check the "DriftGuard server" window.
    goto :fail
)
timeout /t 1 /nobreak >nul
goto :wait

:ready
rem --- 4. Dashboard and demo script ----------------------------------------
echo.
echo Dashboard: %DEMO_URL%
echo Sign in with %DEMO_EMAIL% / %DEMO_PASSWORD% and select the "Live Demo" project.
echo.
start "" "%DEMO_URL%"

".venv\Scripts\python.exe" examples\live_demo.py --base-url "%DEMO_URL%" --email "%DEMO_EMAIL%" --password "%DEMO_PASSWORD%"
if errorlevel 1 goto :fail

echo.
echo The server keeps running in its own window. Close that window to stop it.
pause
exit /b 0

:fail
echo.
echo Demo setup failed. See the messages above.
pause
exit /b 1
