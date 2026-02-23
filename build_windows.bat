@echo off
echo Building Twilio Manager for Windows...
echo.

REM Install PyInstaller if not already installed
python -m pip install pyinstaller

REM Build the executable using Python module
python -m PyInstaller --onefile --windowed --name "TwilioManager" twilio_gui.py

echo.
echo Build complete! Executable is in dist\TwilioManager.exe
echo.
pause
