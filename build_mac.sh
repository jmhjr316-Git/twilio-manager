#!/bin/bash
echo "Building Twilio Manager for Mac..."
echo

# Install PyInstaller if not already installed
pip3 install pyinstaller

# Build the application
pyinstaller --onefile --windowed --name "TwilioManager" twilio_gui.py

echo
echo "Build complete! Application is in dist/TwilioManager.app"
echo "You can drag this to Applications folder"
echo
