@echo off
REM Run the Civitai Download Manager application

REM Change to the directory of this batch file
cd /d "%~dp0civitai-manager"

REM Launch the application with Python (ensure Python is on your PATH)
python main.py

REM Pause to keep the console window open after exit
PAUSE