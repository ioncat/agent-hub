@echo off
chcp 65001 > nul
setlocal

:: ── Paths ─────────────────────────────────────────────────────────────────────
set "SCRIPT_DIR=%~dp0"
set "ROOT=%SCRIPT_DIR%.."
set "KMP_DIR=%ROOT%\..\knowledge-mirror-parser"

:: ── Env vars (override here or use .env file) ─────────────────────────────────
set "DB_PATH=%ROOT%\db\agent.db"
set "KMP_BASE_URL=http://localhost:8001"
:: Candidate name used in CV/Cover filename lookup — change to match your PROFILE.md
if "%CANDIDATE_NAME%"=="" set "CANDIDATE_NAME=Candidate"

echo.
echo  ╔══════════════════════════════════════╗
echo  ║   agent-hub — Vacancy Tracker        ║
echo  ╚══════════════════════════════════════╝
echo.

:: ── Start kmp-service ─────────────────────────────────────────────────────────
echo [1/3] Starting kmp-service on :8001...
start "kmp-service" /MIN cmd /C "cd /d "%KMP_DIR%" && python -m uvicorn api:app --port 8001 --host 127.0.0.1 2>&1"
timeout /t 3 /nobreak > nul

:: Check kmp health
curl -s -o nul -w "%%{http_code}" http://localhost:8001/health | findstr "200" > nul
if errorlevel 1 (
    echo [!] kmp-service did not start. Check the kmp window.
    pause
    exit /b 1
)
echo     kmp-service OK

:: ── Start web tracker ─────────────────────────────────────────────────────────
echo [2/3] Starting web tracker on :8080...
start "web-tracker" /MIN cmd /C "cd /d "%ROOT%" && python -m uvicorn web.api:app --port 8080 --host 127.0.0.1 2>&1"
timeout /t 2 /nobreak > nul

:: ── Open browser ──────────────────────────────────────────────────────────────
echo [3/3] Opening browser...
start http://localhost:8080

echo.
echo  Tracker running at http://localhost:8080
echo  DB: %DB_PATH%
echo.
echo  Close this window to stop (kmp and tracker windows stay open).
echo  To stop all: close the kmp-service and web-tracker windows.
echo.
pause
