# Twilio Manager - Installation Instructions

## Windows Installation

### Step 1: Download
Download `TwilioManager.exe` from the shared location.

### Step 2: Handle Security Warning
When you first run the .exe, Windows will show a security warning:

1. You'll see "Windows protected your PC"
2. Click **"More info"**
3. Click **"Run anyway"**

This warning appears because the app isn't code-signed. It's safe to run - it's just not recognized by Windows SmartScreen yet.

### Step 3: Run the Application
Double-click `TwilioManager.exe` to launch.

---

## Mac Installation

### Step 1: Download
Download `TwilioManager.dmg` from the shared location.

### Step 2: Open the DMG
Double-click `TwilioManager.dmg` to open it.

### Step 3: Install the App
Drag `TwilioManager.app` to your Applications folder (or anywhere you like).

### Step 4: Handle Security Warning
Mac will block the app the first time because it's not notarized:

**Option A - Right-click method (Easiest):**
1. Right-click (or Control-click) on `TwilioManager.app`
2. Select **"Open"** from the menu
3. Click **"Open"** in the dialog that appears
4. The app will launch

**Option B - System Settings method:**
1. Try to open the app normally (it will be blocked)
2. Go to **System Settings** → **Privacy & Security**
3. Scroll down to find "TwilioManager was blocked"
4. Click **"Open Anyway"**
5. Confirm by clicking **"Open"**

After doing this once, the app will open normally in the future.

---

## First Time Setup

### Add Your Twilio Account

1. Click **"Add Account"** button
2. Enter the following information:
   - **Account Name:** A friendly name (e.g., "Dev", "QA", "Prod")
   - **Account SID:** Starts with "AC" (34 characters)
   - **Auth Token:** 32 character hex string

3. Click **"Save"**

Your credentials are stored locally on your computer in:
- Windows: `C:\Users\YOUR-USERNAME\.twilio_gui_config.json`
- Mac: `/Users/YOUR-USERNAME/.twilio_gui_config.json`

### Where to Find Your Twilio Credentials

1. Log in to [Twilio Console](https://console.twilio.com/)
2. Go to your Account Dashboard
3. Find your **Account SID** and **Auth Token**

---

## Using the Application

### Call/Message Lookup Tab
1. Select your account from the dropdown
2. Choose "Calls" or "Messages"
3. Enter a phone number (10 digits or E.164 format like +19193736940)
4. Select date range using the calendar pickers
5. Click **"Fetch Data"**
6. **Double-click any row** to see detailed events/info
7. Click **"Export CSV"** to save results to a spreadsheet

### Inactive Numbers Tab
1. Select your account
2. Set number of days (default: 30)
3. Click **"Find Inactive Numbers"**
4. See which numbers have had no activity

### Number Configuration Tab
1. Select your account (phone numbers load automatically)
2. Select a phone number from the dropdown
3. Click **"Load Configuration"**
4. View all settings for that number

---

## Troubleshooting

**Problem:** Can't open the app on Mac
- **Solution:** Use the right-click → Open method described above

**Problem:** Windows SmartScreen blocks the app
- **Solution:** Click "More info" → "Run anyway"

**Problem:** "Please select an account" error
- **Solution:** Make sure you've added your Twilio account credentials first

**Problem:** No results found
- **Solution:** Check that the phone number is correct and has activity in the selected date range

**Problem:** App crashes or won't start
- **Solution:** Delete the config file and re-add your account:
  - Windows: Delete `C:\Users\YOUR-USERNAME\.twilio_gui_config.json`
  - Mac: Delete `/Users/YOUR-USERNAME/.twilio_gui_config.json`

---

## Support

For issues or questions, contact: [Your contact info or team channel]

## Security Note

Your Twilio credentials are stored locally on your computer only. They are never sent anywhere except directly to Twilio's API when you fetch data.
