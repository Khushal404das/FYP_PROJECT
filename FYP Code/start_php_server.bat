@echo off
title FYP Vehicle Tracking System — PHP Dev Server

echo ============================================================
echo   FYP Vehicle Tracking System
echo   Starting PHP Built-in Web Server...
echo ============================================================
echo.

:: Check PHP
php --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PHP is not installed or not in PATH.
    echo Please install PHP 8.0+ from https://windows.php.net
    pause
    exit /b 1
)

cd /d "%~dp0php_frontend"

echo [INFO] Starting PHP server on http://127.0.0.1:8080
echo [INFO] Open your browser and go to: http://127.0.0.1:8080
echo [INFO] Press Ctrl+C to stop.
echo.

:: Make sure uploads dir exists
if not exist uploads mkdir uploads

php -S 127.0.0.1:8080 -t .

pause
