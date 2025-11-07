# Quick Start Testing Guide

This guide will help you test the `/volunteer` command that was just implemented.

## Prerequisites

Before you start, you need:
1. ✅ Python dependencies installed (already done)
2. 🔧 Discord bot token
3. 🔧 Google Sheets document with service account
4. 🔧 Environment variables configured

---

## Step 1: Create Google Sheets Document

### 1.1 Create New Spreadsheet

1. Go to [Google Sheets](https://sheets.google.com)
2. Create a new spreadsheet
3. Name it "Discord Host Scheduler - Test"

### 1.2 Create Required Sheets

Create these 4 sheets with exact names and headers:

#### Sheet 1: "Schedule"
| date | host_discord_id | host_username | recurring_pattern_id | assigned_at | assigned_by | notes |
|------|-----------------|---------------|---------------------|-------------|-------------|-------|
|      |                 |               |                     |             |             |       |

#### Sheet 2: "RecurringPatterns"
| pattern_id | host_discord_id | host_username | pattern_description | pattern_rule | start_date | end_date | created_at | is_active |
|------------|-----------------|---------------|-------------------|--------------|------------|----------|------------|-----------|
|            |                 |               |                   |              |            |          |            |           |

#### Sheet 3: "AuditLog"
| entry_id | timestamp | action_type | user_discord_id | target_user_discord_id | event_date | recurring_pattern_id | outcome | error_message | metadata |
|----------|-----------|-------------|-----------------|------------------------|------------|---------------------|---------|---------------|----------|
|          |           |             |                 |                        |            |                     |         |               |          |

#### Sheet 4: "Configuration"
| setting_key | setting_value | setting_type | description | updated_at |
|-------------|---------------|--------------|-------------|------------|
| warning_passive_days | 7 | integer | Days before event to post passive warning | |
| warning_urgent_days | 3 | integer | Days before event to post urgent warning | |
| daily_check_time | 09:00 | string | Time of day for daily warning check (PST) | |
| schedule_window_weeks | 8 | integer | Default weeks to show in schedule view | |
| organizer_role_ids | [] | json | Discord role IDs that can use admin commands | |
| host_privileged_role_ids | [] | json | Discord role IDs that can volunteer for others | |
| schedule_channel_id | | string | Discord channel ID for schedule displays | |
| warnings_channel_id | | string | Discord channel ID for warning posts | |
| cache_ttl_seconds | 300 | integer | Cache TTL for Google Sheets data (5 minutes) | |
| max_batch_size | 100 | integer | Maximum rows to batch in Google Sheets API calls | |

### 1.3 Get Spreadsheet ID

From the URL: `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_HERE/edit`

Copy the `SPREADSHEET_ID_HERE` part.

---

## Step 2: Set Up Google Service Account

### 2.1 Create Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable "Google Sheets API":
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Sheets API"
   - Click "Enable"

### 2.2 Create Service Account Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "Service Account"
3. Name it "discord-host-scheduler-bot"
4. Click "Create and Continue"
5. Skip role assignment (click "Continue")
6. Click "Done"

### 2.3 Create Service Account Key

1. Click on the service account you just created
2. Go to "Keys" tab
3. Click "Add Key" > "Create New Key"
4. Choose "JSON" format
5. Click "Create"
6. Save the downloaded JSON file as `service-account-key.json` in your project root

### 2.4 Share Spreadsheet with Service Account

1. Open the JSON key file
2. Find the `client_email` field (looks like `discord-host-scheduler-bot@project-name.iam.gserviceaccount.com`)
3. Go back to your Google Sheets document
4. Click "Share" button
5. Paste the service account email
6. Give it "Editor" permissions
7. Uncheck "Notify people"
8. Click "Share"

---

## Step 3: Create Discord Bot

### 3.1 Create Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Name it "Host Scheduler Bot"
4. Click "Create"

### 3.2 Create Bot

1. Go to "Bot" section in left sidebar
2. Click "Add Bot"
3. Click "Yes, do it!"
4. Under "TOKEN", click "Reset Token" then "Copy"
5. **Save this token** - you'll need it for `.env`

### 3.3 Enable Intents

Under "Privileged Gateway Intents":
- ✅ Enable "Server Members Intent"
- ✅ Enable "Message Content Intent"

Click "Save Changes"

### 3.4 Invite Bot to Your Server

1. Go to "OAuth2" > "URL Generator"
2. Select scopes:
   - ✅ `bot`
   - ✅ `applications.commands`
3. Select bot permissions:
   - ✅ Send Messages
   - ✅ Use Slash Commands
   - ✅ Read Message History
4. Copy the generated URL at the bottom
5. Paste in browser and select your test server
6. Click "Authorize"

---

## Step 4: Configure Environment Variables

Create `.env` file in project root:

```bash
# Discord Bot Configuration
DISCORD_BOT_TOKEN=your_discord_bot_token_from_step_3.2

# Google Sheets Configuration
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id_from_step_1.3
GOOGLE_SHEETS_CREDENTIALS_FILE=service-account-key.json

# Optional: Logging
LOG_LEVEL=INFO
CACHE_TTL_SECONDS=300
```

**Important**: Make sure `.env` is in `.gitignore` (it already is)!

---

## Step 5: Run the Bot

### 5.1 Start the Bot

```bash
cd /Users/zachkysar/projects/language-exchange-bot
/usr/bin/python3 src/bot.py
```

### 5.2 Expected Output

```
{"timestamp": "2025-11-04T...", "level": "INFO", "logger": "discord_host_scheduler", "message": "Initializing Discord Host Scheduler Bot"}
{"timestamp": "2025-11-04T...", "level": "INFO", "logger": "discord_host_scheduler", "message": "Cache service initialized"}
{"timestamp": "2025-11-04T...", "level": "INFO", "logger": "discord_host_scheduler", "message": "Google Sheets service initialized"}
{"timestamp": "2025-11-04T...", "level": "INFO", "logger": "discord_host_scheduler", "message": "Sync service initialized"}
{"timestamp": "2025-11-04T...", "level": "INFO", "logger": "discord_host_scheduler", "message": "Discord service initialized"}
{"timestamp": "2025-11-04T...", "level": "INFO", "logger": "discord_host_scheduler", "message": "Performing startup sync"}
{"timestamp": "2025-11-04T...", "level": "INFO", "logger": "discord_host_scheduler.sync", "message": "Synced 10 configuration entries"}
{"timestamp": "2025-11-04T...", "level": "INFO", "logger": "discord_host_scheduler.sync", "message": "Synced 0 events"}
{"timestamp": "2025-11-04T...", "level": "INFO", "logger": "discord_host_scheduler.discord", "message": "Bot connected as Host Scheduler Bot#1234"}
{"timestamp": "2025-11-04T...", "level": "INFO", "logger": "discord_host_scheduler.discord", "message": "Synced 1 command(s)"}
```

### 5.3 Verify Bot is Online

In Discord, you should see the bot online in your server's member list.

---

## Step 6: Test the /volunteer Command

### Test 1: Volunteer for a Future Date ✅

In Discord, type:
```
/volunteer date:2025-12-25
```

**Expected Result**:
```
✅ You've successfully volunteered to host on Wednesday, December 25, 2025 (PST)
```

**Verify in Google Sheets**:
- Open your "Schedule" sheet
- You should see a new row with:
  - date: `2025-12-25`
  - host_discord_id: your Discord user ID
  - host_username: your Discord username
  - assigned_at: current timestamp

**Verify in AuditLog sheet**:
- New entry with action_type: `VOLUNTEER`
- outcome: `success`

---

### Test 2: Try to Volunteer for Same Date (Conflict) ❌

```
/volunteer date:2025-12-25
```

**Expected Result**:
```
❌ Date Wednesday, December 25, 2025 (PST) is already assigned to @YourUsername (YourUsername#1234). Please choose a different date.
```

---

### Test 3: Invalid Date Format ❌

```
/volunteer date:12/25/2025
```

**Expected Result**:
```
❌ Invalid date format: '12/25/2025'. Expected YYYY-MM-DD (e.g., 2025-11-11)
```

---

### Test 4: Past Date ❌

```
/volunteer date:2020-01-01
```

**Expected Result**:
```
❌ Date must be in the future. Today is 2025-11-04 (PST), you provided 2020-01-01
```

---

### Test 5: Volunteer Someone Else (Proxy Action)

**Note**: This requires host-privileged role. For now, it will fail with permission error.

```
/volunteer date:2025-12-26 user:@SomeOtherUser
```

**Expected Result** (without role):
```
❌ You do not have permission to volunteer on behalf of other users. Required role: host-privileged
```

To make this work:
1. Get a Discord role ID from your server
2. Add it to Configuration sheet: `host_privileged_role_ids` = `["YOUR_ROLE_ID"]`
3. Restart bot
4. Try again - should work!

---

## Step 7: Verify Everything Works

### Checklist:
- [ ] Bot starts without errors
- [ ] Bot syncs configuration from Google Sheets
- [ ] `/volunteer` command appears in Discord
- [ ] Can volunteer for future date successfully
- [ ] Conflict detection works (can't volunteer for taken date)
- [ ] Invalid date formats are rejected
- [ ] Past dates are rejected
- [ ] Google Sheets Schedule is updated
- [ ] AuditLog entries are created
- [ ] Cache is updated (check `cache.json` file)

---

## Troubleshooting

### Bot won't start

**Error: Missing environment variables**
- Check `.env` file exists in project root
- Verify all required variables are set

**Error: Google Sheets credentials file not found**
- Check `service-account-key.json` is in project root
- Verify path in `.env` matches filename

**Error: Authentication failed**
- Re-download service account key
- Verify credentials file is valid JSON

### Bot starts but /volunteer doesn't appear

**Wait 1-2 minutes**
- Discord command sync can take time
- Try typing `/volunteer` manually

**Restart Discord**
- Sometimes Discord client needs refresh

### /volunteer fails with "API error"

**Check Google Sheets sharing**
- Verify service account email has Editor access
- Check sheet names are exactly: "Schedule", "AuditLog", "Configuration"

**Check quota limits**
- Free tier: 100 requests per 100 seconds
- Wait a minute and try again

### Cache issues

**Delete cache.json and restart**
```bash
rm cache.json
/usr/bin/python3 src/bot.py
```

---

## Success! What's Working:

✅ Bot connects to Discord
✅ Bot syncs with Google Sheets
✅ `/volunteer` command registered
✅ Date validation (format, future dates)
✅ Conflict detection (first-wins)
✅ Google Sheets updates
✅ Audit logging
✅ Cache management
✅ PST timezone handling
✅ User-friendly error messages

---

## Next: Phase 4 - View Schedule

Once testing is complete, we'll add the `/schedule` command to view upcoming hosts!
