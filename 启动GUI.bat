@echo off
echo Starting CapsWriter GUI...
venv\Scripts\python.exe tray_gui_launcher.py
if errorlevel 1 (
    echo Failed to start GUI
    pause
)