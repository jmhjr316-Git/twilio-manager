# Twilio Manager GUI

Cross-platform Python GUI for managing and analyzing Twilio call and message logs.

## Features

- **Multi-account management** - Manage Dev/QA/Prod accounts with secure local credential storage
- **Blended call/message retrieval** - Combines TO + FROM results in one view
- **Calendar date pickers** - Easy date range selection
- **CSV export** - Export results to spreadsheet
- **Event viewer** - Double-click any call/message to see detailed events and info
- **Inactive number finder** - Identify numbers with no activity in X days
- **Number configuration viewer** - View Twilio number settings
- **Column sorting** - Click headers to sort by any column

## Requirements

- Python 3.7+
- tkinter (usually included with Python)
- See requirements.txt for Python packages

## Installation

### For End Users

See [INSTALLATION.md](INSTALLATION.md) for detailed installation instructions including how to handle security warnings on Windows and Mac.

### For Developers

```bash
pip install -r requirements.txt
```

## Usage

```bash
python twilio_gui.py
```

### First Time Setup

1. Click "Add Account" to add your Twilio credentials
2. Enter Account Name (e.g., "Dev", "QA", "Prod")
3. Enter Account SID (starts with AC)
4. Enter Auth Token (32 character hex string)

Credentials are stored locally in `~/.twilio_gui_config.json` (base64 encoded).

### Call/Message Lookup

1. Select account
2. Choose "Calls" or "Messages"
3. Enter phone number (E.164 format or 10 digits)
4. Select date range
5. Click "Fetch Data"
6. Double-click any row to see detailed events

### Find Inactive Numbers

1. Select account
2. Set number of days
3. Click "Find Inactive Numbers"

### View Number Configuration

1. Select account (phone numbers load automatically)
2. Select phone number from dropdown
3. Click "Load Configuration"

## Security Note

Never commit the `.twilio_gui_config.json` file - it contains your Twilio credentials.

## Platform Support

- Windows
- macOS
- Linux
