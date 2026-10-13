@echo off
title FYP Vehicle Tracking System — Python API Server

echo ============================================================
echo   FYP Vehicle Tracking System
echo   Starting Python Flask API Server...
echo ============================================================
echo.

cd /d "%~dp0python_backend"

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

:: Install dependencies if needed
echo [INFO] Checking dependencies...
pip install -r requirements.txt --quiet

echo.
echo [INFO] Starting API server on http://127.0.0.1:5000
echo [INFO] Press Ctrl+C to stop.
echo.

python api_server.py

pause
