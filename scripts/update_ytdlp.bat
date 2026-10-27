@echo off
setlocal
cd /d "%~dp0\.."

if exist "backend\venv\Scripts\python.exe" (
    echo Using backend virtual environment...
    "backend\venv\Scripts\python.exe" scripts\update_ytdlp.py
) else (
    echo Using system Python...
    python scripts\update_ytdlp.py
)

pause
