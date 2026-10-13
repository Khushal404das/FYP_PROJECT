@echo off
title FYP Vehicle Tracking System — Full Launch

echo ============================================================
echo   FYP Vehicle Tracking System — Full Launch
echo ============================================================
echo.
echo This will open two windows:
echo   1. Python API Server  (http://127.0.0.1:5000)
echo   2. PHP Web Frontend   (http://127.0.0.1:8080)
echo.

:: Start Python API server in a new window
start "FYP API Server" cmd /c "%~dp0start_api_server.bat"

:: Wait 3 seconds for Flask to boot
timeout /t 3 /nobreak >nul

:: Start PHP server in a new window
start "FYP PHP Frontend" cmd /c "%~dp0start_php_server.bat"

:: Wait 2 seconds then open browser
timeout /t 2 /nobreak >nul
start http://127.0.0.1:8080

echo.
echo [OK] Both servers started. Browser opening...
echo [OK] Dashboard: http://127.0.0.1:8080/dashboard.php
echo.
pause
