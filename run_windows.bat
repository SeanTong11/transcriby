@echo off
REM SlowPlay Windows Launcher
REM This script sets up the environment and launches SlowPlay

echo Starting SlowPlay...

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher from https://python.org
    pause
    exit /b 1
)

REM Launch SlowPlay
python sp-launch.py %*

if errorlevel 1 (
    echo.
    echo SlowPlay exited with an error.
    pause
)
