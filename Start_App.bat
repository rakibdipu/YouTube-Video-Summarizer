@echo off
title Video Summarizer
echo =========================================
echo Starting Video Summarizer GUI...
echo =========================================
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo Virtual environment activated!
)
echo Launching App...
python gui.py
pause
