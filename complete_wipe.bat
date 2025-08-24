@echo off
REM Complete Wipe Batch Script for CivitAI Download Manager
REM This script will perform a complete reset of all application data

title CivitAI Download Manager - Complete Data Wipe

REM Change to the script directory
cd /d "%~dp0"

echo.
echo ============================================================
echo CivitAI Download Manager - Complete Data Wipe
echo ============================================================
echo.
echo This will completely reset the application to factory defaults.
echo Please ensure the application is NOT RUNNING before proceeding.
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python and try again.
    echo.
    pause
    exit /b 1
)

REM Check if the wipe script exists
if not exist "complete_wipe.py" (
    echo ERROR: complete_wipe.py not found in current directory.
    echo Please ensure you're running this from the correct folder.
    echo.
    pause
    exit /b 1
)

REM Execute the Python wipe script
echo Running complete data wipe script...
echo.
python complete_wipe.py

REM Check if the script ran successfully
if errorlevel 1 (
    echo.
    echo ERROR: The wipe script encountered an error.
    echo Please check the output above for details.
) else (
    echo.
    echo SUCCESS: Data wipe completed successfully.
)

echo.
pause
