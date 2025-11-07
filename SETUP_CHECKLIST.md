# Quick Setup Checklist ✅

Follow along and check off each item!

## Part 1: Discord Bot (5 min)
- [ ] Go to https://discord.com/developers/applications
- [ ] Create new application → name it "Host Scheduler Bot"
- [ ] Add Bot (Bot section in sidebar)
- [ ] Enable "Server Members Intent" and "Message Content Intent"
- [ ] Copy bot token → save it somewhere safe
- [ ] Generate invite URL (OAuth2 → URL Generator)
  - [ ] Select: `bot` + `applications.commands`
  - [ ] Select: Send Messages, Use Slash Commands
- [ ] Invite bot to your Discord server
- [ ] Verify bot appears (offline) in member list

## Part 2: Google Sheets (3 min)
- [ ] Go to https://sheets.google.com
- [ ] Create new spreadsheet → name it "Discord Host Scheduler"
- [ ] Create 4 sheets (rename + add new):
  - [ ] Schedule
  - [ ] RecurringPatterns
  - [ ] AuditLog
  - [ ] Configuration
- [ ] Copy headers from `setup_sheets_template.md` into each sheet
- [ ] Copy configuration data into Configuration sheet (10 rows)
- [ ] Copy Spreadsheet ID from URL (the long part between /d/ and /edit)

## Part 3: Google Service Account (5 min)
- [ ] Go to https://console.cloud.google.com
- [ ] Create project → name it "discord-host-scheduler"
- [ ] Enable Google Sheets API (APIs & Services → Library)
- [ ] Create Service Account (APIs & Services → Credentials)
  - [ ] Name: "discord-bot"
  - [ ] Skip permissions
- [ ] Create JSON key (Keys tab → Add Key)
- [ ] Download JSON file
- [ ] Move to project folder: `mv ~/Downloads/discord-*.json ./service-account-key.json`
- [ ] Get service account email: `cat service-account-key.json | grep client_email`
- [ ] Share Google Sheet with service account email (Editor access)

## Part 4: Configure .env (1 min)
- [ ] Open .env file
- [ ] Paste Discord bot token
- [ ] Paste Spreadsheet ID
- [ ] Save file

## Part 5: Test! (1 min)
- [ ] Run: `./QUICK_TEST.sh`
- [ ] Run: `/usr/bin/python3 src/bot.py`
- [ ] Check bot is online in Discord
- [ ] Test: `/volunteer date:2025-12-25`
- [ ] Check Google Sheets for new row

---

**Total Time**: ~15 minutes
**Difficulty**: Easy (just copy-paste!)

See `SETUP_FROM_SCRATCH.md` for detailed instructions for each step.
