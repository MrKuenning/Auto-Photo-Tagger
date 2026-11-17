@echo off
title Auto Photo Tagger (Console)
cd /d "%~dp0"
call venv\Scripts\activate.bat
python app\main.py
pause
