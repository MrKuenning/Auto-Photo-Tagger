@echo off
cd /d "%~dp0"
if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" app\main.py
) else (
    call venv\Scripts\activate.bat
    start "" pythonw app\main.py
)
