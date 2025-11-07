# Setup Guide: Discord Host Scheduler Bot

Complete guide to setting up and running the Discord Host Scheduler Bot.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Setup](#quick-setup)
3. [Detailed Setup Steps](#detailed-setup-steps)
4. [Running the Bot](#running-the-bot)
5. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, ensure you have:

- **Python 3.11+** installed
- **Discord Developer Account** (free at https://discord.com/developers/applications)
- **Google Cloud Project** with Sheets API enabled
- **Google Service Account** with credentials JSON file
- **Google Spreadsheet** created and shared with your service account email

---

## Quick Setup

For experienced users who want to get started quickly:

```bash
# 1. Clone and install
git clone <repository-url>
cd language-exchange-bot
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 3. Set up Google Sheets
python3 scripts/setup_google_sheets.py

# 4. Run the bot
python3 -m src.bot
```

---

## Detailed Setup Steps

### Step 1: Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt
```

**Required packages:**
- `discord.py` - Discord API wrapper
- `gspread` - Google Sheets API wrapper
- `google-auth` - Google authentication
- `python-dotenv` - Environment variable management

### Step 2: Create Discord Bot

1. Go to https://discord.com/developers/applications
2. Click "New Application" and give it a name
3. Go to the "Bot" section in the left sidebar
4. Click "Reset Token" and copy the token (save this securely!)
5. **Enable Privileged Gateway Intents:**
   - ✅ SERVER MEMBERS INTENT
   - ✅ MESSAGE CONTENT INTENT
6. Go to OAuth2 → URL Generator
7. Select scopes:
   - ✅ `bot`
   - ✅ `applications.commands`
8. Select bot permissions:
   - ✅ Send Messages
   - ✅ Use Slash Commands
   - ✅ Read Message History
9. Copy the generated URL and use it to invite the bot to your server

### Step 3: Set Up Google Sheets

#### A. Create Google Service Account

1. Go to https://console.cloud.google.com
2. Create a new project or select an existing one
3. Enable the Google Sheets API:
   - Go to "APIs & Services" → "Library"
   - Search for "Google Sheets API"
   - Click "Enable"
4. Create Service Account:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "Service Account"
   - Fill in the details and click "Create"
   - Skip optional steps and click "Done"
5. Generate credentials:
   - Click on the created service account
   - Go to "Keys" tab
   - Click "Add Key" → "Create New Key"
   - Choose JSON format
   - Download the file and save it securely (e.g., `credentials.json`)

#### B. Create Google Spreadsheet

1. Go to https://sheets.google.com
2. Create a new spreadsheet
3. Name it (e.g., "Discord Host Scheduler")
4. Copy the Spreadsheet ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_HERE/edit
   ```
5. **Share the spreadsheet with your service account:**
   - Click "Share" button
   - Paste the service account email (from the JSON file: `client_email`)
   - Give it "Editor" permissions
   - Uncheck "Notify people" and click "Share"

#### C. Automated Sheet Setup

Run the automated setup script to create all required sheets with proper structure:

```bash
python3 scripts/setup_google_sheets.py
```

This script will:
- Create 4 required sheets: Configuration, Schedule, RecurringPatterns, AuditLog
- Add proper headers to each sheet
- Populate Configuration sheet with default settings
- Verify everything is set up correctly

**The script is safe to run multiple times** - it will only create missing sheets and data.

### Step 4: Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and fill in your credentials:
   ```env
   # Discord Bot Configuration
   DISCORD_BOT_TOKEN=your_discord_bot_token_here

   # Google Sheets Configuration
   GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id_here
   GOOGLE_SHEETS_CREDENTIALS_FILE=path/to/credentials.json

   # Optional: Cache settings
   CACHE_TTL_SECONDS=300
   ```

3. Ensure your credentials file path is correct and the file exists

### Step 5: Verify Setup

Before running the bot, verify your setup:

```bash
# Check Python version
python3 --version  # Should be 3.11+

# Check dependencies
pip list | grep discord.py
pip list | grep gspread

# Verify .env file exists and has required variables
cat .env
```

---

## Running the Bot

### Development Mode

Run the bot directly for development and testing:

```bash
python3 -m src.bot
```

You should see output like:
```
{"level": "INFO", "message": "Initializing Discord Host Scheduler Bot"}
{"level": "INFO", "message": "Bot connected as YourBotName#1234"}
{"level": "INFO", "message": "Synced 2 command(s)"}
```

### Production Mode

For production deployment, consider:

#### Option 1: systemd Service (Linux)

Create `/etc/systemd/system/discord-bot.service`:

```ini
[Unit]
Description=Discord Host Scheduler Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/language-exchange-bot
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 -m src.bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable discord-bot
sudo systemctl start discord-bot
sudo systemctl status discord-bot
```

#### Option 2: Docker (Coming Soon)

Docker support will be added in a future update.

#### Option 3: Screen/tmux

Simple production setup using screen:

```bash
# Start a screen session
screen -S discord-bot

# Run the bot
python3 -m src.bot

# Detach with Ctrl+A, then D
# Reattach with: screen -r discord-bot
```

---

## Troubleshooting

### Bot Fails to Start

#### "Missing required environment variables"
- Check that `.env` file exists in the project root
- Verify all required variables are set (DISCORD_BOT_TOKEN, GOOGLE_SHEETS_SPREADSHEET_ID, GOOGLE_SHEETS_CREDENTIALS_FILE)

#### "Improper token has been passed"
- Your Discord bot token is invalid
- Generate a new token in Discord Developer Portal → Bot → Reset Token

#### "PrivilegedIntentsRequired"
- Enable required intents in Discord Developer Portal:
  - Bot → Privileged Gateway Intents
  - Enable "SERVER MEMBERS INTENT" and "MESSAGE CONTENT INTENT"

#### "Spreadsheet not found"
- Verify the Spreadsheet ID in `.env` is correct
- Ensure the spreadsheet is shared with your service account email
- Check that the service account has "Editor" permissions

#### "WorksheetNotFound: Schedule" (or other sheet names)
- Run the setup script: `python3 scripts/setup_google_sheets.py`
- This will create all required sheets automatically

### Google Sheets Sync Issues

#### "Failed to sync configuration"
- Check that the Configuration sheet exists and has headers
- Verify the service account has edit permissions
- Run `python3 scripts/setup_google_sheets.py` to fix structure

#### "Authentication failed"
- Verify credentials file path in `.env` is correct
- Check that the credentials file is valid JSON
- Ensure the service account hasn't been deleted

### Discord Command Issues

#### Commands don't appear in Discord
- Wait 1-2 minutes for Discord to sync global commands
- Check bot logs for "Synced X command(s)" message
- Verify bot has proper permissions in your server

#### "Bot not responding to commands"
- Check bot is online in Discord
- Verify bot has "Use Slash Commands" permission in the channel
- Check bot logs for error messages

### Performance Issues

#### "Bot is slow to respond"
- Adjust `CACHE_TTL_SECONDS` in `.env` (default: 300)
- Check Google Sheets API quota limits
- Consider optimizing sheet size (remove old audit log entries)

---

## Configuration

After setup, you can customize bot behavior in the Google Sheets Configuration tab:

| Setting | Default | Description |
|---------|---------|-------------|
| `warning_passive_days` | 7 | Days before event to post passive warning |
| `warning_urgent_days` | 3 | Days before event to post urgent warning |
| `daily_check_time` | 09:00 | Time for daily warning check (PST) |
| `schedule_window_weeks` | 8 | Default weeks shown in schedule view |
| `cache_ttl_seconds` | 300 | Cache duration for Sheets data |

To modify settings:
1. Open your Google Spreadsheet
2. Go to the "Configuration" tab
3. Edit the `setting_value` column
4. The bot will pick up changes on next sync (within cache TTL)

---

## Next Steps

Once your bot is running:

1. **Test the commands in Discord:**
   - `/schedule` - View upcoming host schedule
   - `/volunteer` - Sign up to host on a date

2. **Configure role permissions:**
   - Add Discord role IDs to Configuration sheet
   - `organizer_role_ids` - Can use admin commands
   - `host_privileged_role_ids` - Can volunteer for others

3. **Set up notification channels:**
   - Add channel IDs to Configuration sheet
   - `schedule_channel_id` - For schedule displays
   - `warnings_channel_id` - For warning posts

4. **Read the user guide:**
   - See `COMMANDS.md` for full command reference
   - See `TROUBLESHOOTING.md` for common issues

---

## Getting Help

If you encounter issues not covered in this guide:

1. Check the logs for error messages
2. Review `TROUBLESHOOTING.md` for detailed solutions
3. Check the GitHub Issues page
4. Join the support Discord server (link in README)

---

## Security Notes

- **Never commit `.env` file or credentials to git**
- Keep your Discord bot token secret
- Restrict Google Service Account permissions to only what's needed
- Regularly rotate credentials
- Use environment variables for all sensitive data
