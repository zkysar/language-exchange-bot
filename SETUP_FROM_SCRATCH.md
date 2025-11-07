# Complete Setup Guide - Starting from Nothing

**Time Required**: ~15-20 minutes
**Difficulty**: Easy (just follow the steps!)

---

## Part 1: Create Discord Bot (5 minutes)

### Step 1.1: Create Discord Application

1. **Open**: https://discord.com/developers/applications
2. **Click**: "New Application" (top right)
3. **Name**: "Host Scheduler Bot" (or any name you like)
4. **Click**: "Create"

✅ **Checkpoint**: You should now see your application dashboard

---

### Step 1.2: Create the Bot

1. **Click**: "Bot" in left sidebar
2. **Click**: "Add Bot"
3. **Click**: "Yes, do it!"

✅ **Checkpoint**: You should see "A wild bot has appeared!"

---

### Step 1.3: Configure Bot Settings

**Under "Privileged Gateway Intents" section:**

1. ✅ **Enable**: "Server Members Intent" (toggle ON)
2. ✅ **Enable**: "Message Content Intent" (toggle ON)
3. **Click**: "Save Changes"

✅ **Checkpoint**: Both toggles should be GREEN/ON

---

### Step 1.4: Get Your Bot Token

⚠️ **IMPORTANT**: This token is SECRET - don't share it!

1. **Scroll up** to "TOKEN" section
2. **Click**: "Reset Token"
3. **Click**: "Yes, do it!"
4. **Click**: "Copy" button
5. **Save this somewhere safe** (you'll paste it in .env soon)

✅ **Checkpoint**: You have a long token copied (starts with something like `MTEx...`)

---

### Step 1.5: Invite Bot to Your Server

**Need a test server?**
- If you don't have one, create a new Discord server first (click + in Discord, "Create My Own")

**Generate Invite URL:**

1. **Click**: "OAuth2" in left sidebar
2. **Click**: "URL Generator" (sub-menu)
3. **Under SCOPES**, check:**
   - ✅ `bot`
   - ✅ `applications.commands`
4. **Under BOT PERMISSIONS**, check:**
   - ✅ Send Messages
   - ✅ Read Messages/View Channels
   - ✅ Use Slash Commands
   - ✅ Read Message History
5. **Scroll down**, copy the **Generated URL**
6. **Paste URL in browser**, select your test server
7. **Click**: "Authorize"

✅ **Checkpoint**: Bot should appear OFFLINE in your server's member list

---

## Part 2: Create Google Sheets Document (3 minutes)

### Step 2.1: Create New Spreadsheet

1. **Open**: https://sheets.google.com
2. **Click**: "Blank" to create new spreadsheet
3. **Name it**: "Discord Host Scheduler" (top-left)

✅ **Checkpoint**: You have a blank spreadsheet open

---

### Step 2.2: Create Required Sheets

You need 4 sheets total. By default you have 1 sheet.

**Rename Sheet1:**
1. Right-click "Sheet1" tab at bottom
2. Click "Rename"
3. Type: `Schedule`
4. Press Enter

**Add 3 more sheets:**
1. Click "+" button next to sheet tabs (bottom-left)
2. Name it: `RecurringPatterns`
3. Click "+" again, name: `AuditLog`
4. Click "+" again, name: `Configuration`

✅ **Checkpoint**: You should see 4 tabs at bottom: Schedule, RecurringPatterns, AuditLog, Configuration

---

### Step 2.3: Add Headers to Each Sheet

**IMPORTANT**: Headers must be exact (copy-paste them!)

#### Sheet: Schedule

1. Click on "Schedule" tab
2. Click cell A1
3. Paste this row:

```
date	host_discord_id	host_username	recurring_pattern_id	assigned_at	assigned_by	notes
```

#### Sheet: RecurringPatterns

1. Click "RecurringPatterns" tab
2. Click cell A1
3. Paste this row:

```
pattern_id	host_discord_id	host_username	pattern_description	pattern_rule	start_date	end_date	created_at	is_active
```

#### Sheet: AuditLog

1. Click "AuditLog" tab
2. Click cell A1
3. Paste this row:

```
entry_id	timestamp	action_type	user_discord_id	target_user_discord_id	event_date	recurring_pattern_id	outcome	error_message	metadata
```

#### Sheet: Configuration

1. Click "Configuration" tab
2. Click cell A1
3. Paste HEADERS:

```
setting_key	setting_value	setting_type	description	updated_at
```

4. **Now paste the configuration DATA** (click cell A2, then paste):

```
warning_passive_days	7	integer	Days before event to post passive warning
warning_urgent_days	3	integer	Days before event to post urgent warning
daily_check_time	09:00	string	Time of day for daily warning check (PST)
schedule_window_weeks	8	integer	Default weeks to show in schedule view
organizer_role_ids	[]	json	Discord role IDs that can use admin commands
host_privileged_role_ids	[]	json	Discord role IDs that can volunteer for others
schedule_channel_id		string	Discord channel ID for schedule displays
warnings_channel_id		string	Discord channel ID for warning posts
cache_ttl_seconds	300	integer	Cache TTL for Google Sheets data (5 minutes)
max_batch_size	100	integer	Maximum rows to batch in Google Sheets API calls
```

✅ **Checkpoint**: Configuration sheet should have 11 rows (1 header + 10 data rows)

---

### Step 2.4: Get Spreadsheet ID

1. Look at the URL in your browser
2. It looks like: `https://docs.google.com/spreadsheets/d/LONG_ID_HERE/edit`
3. **Copy the LONG_ID_HERE part** (between `/d/` and `/edit`)
4. **Save it** - you'll need it soon!

✅ **Checkpoint**: You have a long ID copied (looks like `1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms`)

---

## Part 3: Create Google Service Account (5 minutes)

This allows the bot to access your Google Sheets.

### Step 3.1: Go to Google Cloud Console

1. **Open**: https://console.cloud.google.com/
2. **Sign in** with your Google account (same one used for Sheets)

---

### Step 3.2: Create New Project

1. **Click** the project dropdown (top-left, says "Select a project")
2. **Click**: "NEW PROJECT" (top-right)
3. **Project name**: "discord-host-scheduler"
4. **Click**: "CREATE"
5. **Wait** ~10 seconds for it to create
6. **Click** "SELECT PROJECT" when it appears

✅ **Checkpoint**: Top bar should show "discord-host-scheduler"

---

### Step 3.3: Enable Google Sheets API

1. **Click** "☰" menu (top-left)
2. **Hover over**: "APIs & Services"
3. **Click**: "Library"
4. **Search for**: "Google Sheets API"
5. **Click** on "Google Sheets API" result
6. **Click**: "ENABLE"
7. **Wait** for it to enable (~5 seconds)

✅ **Checkpoint**: You should see "API enabled" with a green checkmark

---

### Step 3.4: Create Service Account

1. **Click** "☰" menu (top-left)
2. **Hover over**: "APIs & Services"
3. **Click**: "Credentials"
4. **Click**: "+ CREATE CREDENTIALS" (top)
5. **Select**: "Service account"
6. **Service account name**: "discord-bot"
7. **Service account ID**: auto-filled (leave it)
8. **Click**: "CREATE AND CONTINUE"
9. **Skip** the "Grant this service account access" section → Click "CONTINUE"
10. **Skip** "Grant users access" section → Click "DONE"

✅ **Checkpoint**: You should see your service account listed

---

### Step 3.5: Create JSON Key

1. **Click** on the service account you just created (in the list)
2. **Click** "KEYS" tab (top)
3. **Click**: "ADD KEY" → "Create new key"
4. **Select**: "JSON"
5. **Click**: "CREATE"
6. **File downloads automatically!** (named something like `discord-host-scheduler-xxxxx.json`)

✅ **Checkpoint**: A JSON file should have downloaded to your Downloads folder

---

### Step 3.6: Move the JSON Key File

**Open Terminal** and run:

```bash
# Move the downloaded file to your project folder
cd /Users/zachkysar/projects/language-exchange-bot
mv ~/Downloads/discord-host-scheduler-*.json ./service-account-key.json
ls -la service-account-key.json
```

✅ **Checkpoint**: You should see the file listed

---

### Step 3.7: Get Service Account Email

**Open the JSON file to find the email:**

```bash
cat service-account-key.json | grep client_email
```

**Copy the email** (looks like `discord-bot@discord-host-scheduler.iam.gserviceaccount.com`)

---

### Step 3.8: Share Google Sheets with Service Account

1. **Go back** to your Google Sheets document
2. **Click**: "Share" button (top-right)
3. **Paste** the service account email
4. **Make sure** it says "Editor" (not Viewer)
5. **Uncheck** "Notify people"
6. **Click**: "Share"

✅ **Checkpoint**: Service account email should appear under "People with access"

---

## Part 4: Configure .env File (2 minutes)

Now let's put it all together!

**Edit the .env file:**

```bash
cd /Users/zachkysar/projects/language-exchange-bot
nano .env
```

**Replace the placeholders with YOUR values:**

1. `PASTE_YOUR_DISCORD_BOT_TOKEN_HERE` → Your Discord bot token from Part 1
2. `PASTE_YOUR_SPREADSHEET_ID_HERE` → Your spreadsheet ID from Part 2

**Press** Ctrl+X, then Y, then Enter to save

---

## Part 5: Test It! (2 minutes)

### Step 5.1: Run Pre-flight Check

```bash
./QUICK_TEST.sh
```

**Expected output:**
```
✅ .env file found
✅ Service account credentials found
✅ No syntax errors found
✅ All unit tests passed
```

---

### Step 5.2: Start the Bot

```bash
/usr/bin/python3 src/bot.py
```

**Expected output (after a few seconds):**
```json
{"timestamp": "...", "level": "INFO", "message": "Bot connected as Host Scheduler Bot#1234"}
{"timestamp": "...", "level": "INFO", "message": "Synced 1 command(s)"}
```

✅ **Checkpoint**: Bot should show as ONLINE in Discord!

---

### Step 5.3: Test /volunteer Command

**In Discord**, type:
```
/volunteer date:2025-12-25
```

**Expected response:**
```
✅ You've successfully volunteered to host on Wednesday, December 25, 2025 (PST)
```

**Check Google Sheets**:
- Open your "Schedule" sheet
- You should see a new row with your assignment!

---

## 🎉 Success!

If you got here, everything is working!

**What you can do now:**
- `/volunteer date:YYYY-MM-DD` - Volunteer for a date
- `/schedule` - View upcoming schedule
- `/schedule weeks:4` - View 4 weeks
- `/schedule date:2025-12-25` - Check specific date

---

## ❌ Troubleshooting

### Bot won't start

**Error: "Missing required environment variables"**
→ Check your .env file has all values filled in

**Error: "credentials file not found"**
→ Make sure `service-account-key.json` is in the project root

**Error: "Authentication failed"**
→ Re-download the service account key and replace the file

### /volunteer doesn't work

**"Permission denied" or "API error"**
→ Make sure you shared the Google Sheet with the service account email

**"Command not found"**
→ Wait 1-2 minutes for Discord to sync commands, or restart Discord

### Other issues

Check `bot.log` file for detailed error messages:
```bash
tail -20 bot.log
```

---

Need help? The error messages in the logs usually point to exactly what's wrong!
