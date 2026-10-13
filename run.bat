@echo off
title Vision-Mixer AI Command Center - FAST NUCES
echo ====================================================================
echo   VISION-MIXER AI COMMAND CENTER (FAST NUCES FYP)
echo   Agent-Based Multi-Camera Vehicle Tracking System
echo ====================================================================
echo.
echo [1/2] Starting PHP Web Server at http://127.0.0.1:8000 ...
start "" http://127.0.0.1:8000/
php -S 127.0.0.1:8000 -t Final\php\public
