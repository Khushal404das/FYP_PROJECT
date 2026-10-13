@echo off
title Vision-Mixer Project Launcher
color 0A
cls
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║     VISION-MIXER AI SURVEILLANCE — FAST NUCES FYP       ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.
echo  Starting all components...
echo.

cd /d d:\FYP_project\FYP_PROJECT\Final

echo  [1/2] Opening Python PyQt5 Detection App...
start "Python App — YOLOv8 Vehicle Detection" cmd /k "cd /d d:\FYP_project\FYP_PROJECT\Final && python app.py"

timeout /t 2 /nobreak >nul

echo  [2/2] Opening Browser (PHP Dashboard)...
start "" "http://127.0.0.1:8000/index.php"

echo.
echo  ══════════════════════════════════════════════
echo   Python App  : PyQt5 window (check taskbar)
echo   PHP Web     : http://127.0.0.1:8000
echo   Search Page : http://127.0.0.1:8000/search.php
echo  ══════════════════════════════════════════════
echo.
echo  Press any key to close this launcher...
pause >nul
