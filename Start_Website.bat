@echo off
title Video Summarizer Web UI
echo =========================================
echo Starting Video Summarizer Local Website...
echo =========================================
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)
echo Starting Server...
python server.py
pause
