@echo off
setlocal
cd /d "%~dp0"
where docker >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Docker Desktop is not installed or not available in PATH.
  echo Install Docker Desktop, start it, and run this file again.
  pause
  exit /b 1
)
if not exist .env (
  if exist .env.example (
    copy .env.example .env >nul
    echo Created .env from .env.example. Review it before using outside local development.
  )
)
docker compose version >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Docker Compose v2 is required.
  pause
  exit /b 1
)
echo Starting database and web application. Re-running this command is safe.
docker compose up --build -d
if errorlevel 1 (
  echo [ERROR] Startup failed. Recent logs:
  docker compose logs --tail=100
  pause
  exit /b 1
)
echo.
if "%WEB_PORT%"=="" (echo Application: http://localhost:8000) else (echo Application: http://localhost:%WEB_PORT%)
echo To inspect logs: docker compose logs -f
pause
endlocal
