@echo off
echo Building Twilio Manager for Windows...
echo.

REM Install PyInstaller if not already installed
pip install pyinstaller

REM Build the executable
pyinstaller --onefile --windowed --name "TwilioManager" --icon=NONE twilio_gui.py

echo.
echo Build complete! Executable is in dist\TwilioManager.exe
echo.
pause
