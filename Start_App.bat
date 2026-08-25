@echo off
title Video Summarizer
echo =========================================
echo Starting Video Summarizer GUI...
echo =========================================
cd /d "R:\video-summarizer\video-summarizer"
call .venv\Scripts\activate.bat
echo Virtual environment activated!
echo Launching App...
python gui.py
pause
