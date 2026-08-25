@echo off
title Video Summarizer Web UI
echo =========================================
echo Starting Video Summarizer Local Website...
echo =========================================
cd /d "R:\video-summarizer\video-summarizer"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo Starting Server...
.venv\Scripts\python.exe server.py
pause
