# Quickstart Guide: Discord Host Scheduler Bot

**Date**: 2025-11-04  
**Feature**: 001-discord-host-scheduler

## Overview

This guide provides quick-start instructions for setting up and using the Discord Host Scheduler Bot. For detailed setup instructions, see `docs/SETUP.md`. For command reference, see `docs/COMMANDS.md`.

---

## Prerequisites

- Python 3.11 or higher
- Discord bot token (from Discord Developer Portal)
- Google Sheets document with required sheets
- Google Service Account credentials (JSON key file)

---

## Quick Setup (5 minutes)

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create `.env` file:

```bash
# Discord Bot Configuration
DISCORD_BOT_TOKEN=your_discord_bot_token_here

# Google Sheets Configuration
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id_here
GOOGLE_SHEETS_CREDENTIALS_FILE=path/to/service-account-key.json

# Optional: Logging
LOG_LEVEL=INFO
```

### 3. Set Up Google Sheets

Create a Google Sheets document with these sheets:
- **Schedule**: Headers: `date`, `host_discord_id`, `host_username`, `recurring_pattern_id`, `assigned_at`, `assigned_by`, `notes`
- **RecurringPatterns**: Headers: `pattern_id`, `host_discord_id`, `host_username`, `pattern_description`, `pattern_rule`, `start_date`, `end_date`, `created_at`, `is_active`
- **AuditLog**: Headers: `entry_id`, `timestamp`, `action_type`, `user_discord_id`, `target_user_discord_id`, `event_date`, `recurring_pattern_id`, `outcome`, `error_message`, `metadata`
- **Configuration**: Headers: `setting_key`, `setting_value`, `setting_type`, `description`, `updated_at`

Share the spreadsheet with your service account email (found in the JSON key file).

### 4. Run the Bot

```bash
python src/main.py
```

The bot will:
- Connect to Discord
- Sync with Google Sheets
- Register slash commands
- Start scheduled warning checks

---

## Common Integration Scenarios

### Scenario 1: First-Time Setup

**Goal**: Get the bot running and verify it works.

**Steps**:
1. Create Google Sheets document with required sheets (see above)
2. Set up Discord bot in Developer Portal
3. Invite bot to your Discord server with `applications.commands` scope
4. Configure environment variables
5. Run bot: `python src/main.py`
6. Test: Run `/help` in Discord to verify commands registered

**Expected Result**: Bot responds with help text showing all available commands.

---

### Scenario 2: Volunteer for a Date

**Goal**: A host volunteers to host an upcoming meetup.

**Steps**:
1. Host types `/volunteer ` and the Discord autocomplete dropdown populates the `date:` parameter with the next N open (unassigned) dates
2. Host selects a date from the dropdown: `/volunteer user:@self date:2025-11-11`
3. Bot verifies the selected date is still open (heartbeat-locked, under in-process `asyncio.Lock`)
4. Bot updates Google Sheets Schedule sheet
5. Bot sends confirmation message

**Expected Result**: 
- Host receives confirmation: "Successfully assigned @user to host on Tuesday, November 11, 2025 (America/Los_Angeles)"
- Google Sheets updated with host assignment
- Audit log entry created (buffered; flushed within 30s or at 50-entry threshold)

**Error Cases**:
- Date already assigned (raced between autocomplete and submit): Bot shows current host and suggests alternatives
- No open dates: Autocomplete dropdown is empty

---

### Scenario 3: Set Up Recurring Pattern

**Goal**: A host commits to hosting regularly (e.g., every 2nd Tuesday).

**Steps**:
1. Host runs: `/volunteer recurring pattern:"every 2nd Tuesday"`
2. Bot parses pattern and generates preview (next 3 months)
3. Bot checks for conflicts with existing assignments
4. Bot shows preview and asks for confirmation
5. Host confirms: `yes`
6. Bot assigns all non-conflicting dates to Google Sheets

**Expected Result**:
- Preview shows: "This pattern will assign you to: Tuesday, Nov 11, Nov 25, Dec 9, ..."
- After confirmation: All dates assigned, recurring pattern created
- Future dates automatically assigned (if pattern generates them)

**Error Cases**:
- Invalid pattern: Bot shows pattern format examples
- All dates conflicted: Bot shows conflicts and suggests alternatives

---

### Scenario 4: View Schedule

**Goal**: Community members want to see who's hosting upcoming meetups.

**Steps**:
1. User runs: `/schedule weeks:8`
2. Bot queries Google Sheets (or cache if recent)
3. Bot formats schedule as embed

**Expected Result**:
- Embed showing next 8 weeks with assigned hosts
- Unassigned dates clearly marked: "[Unassigned]"
- Dates formatted in `America/Los_Angeles` (DST handled automatically)

**Performance**: Response within 3 seconds for 12 weeks of data.

---

### Scenario 5: Warning System

**Goal**: Bot automatically warns about unassigned dates approaching.

**Setup**:
- Configure `warning_passive_days` (default: 7)
- Configure `warning_urgent_days` (default: 3)
- Configure `warnings_channel_id` in Configuration sheet

**Automated Flow**:
1. Bot runs daily check at configured time (default: 09:00 `America/Los_Angeles`)
2. Bot queries unassigned dates from Schedule sheet
3. Bot calculates days until each unassigned date
4. Bot posts warnings:
   - Passive (7+ days): Regular message in warnings channel
   - Urgent (3 days): Urgent message pinging host and admin roles

**Manual Trigger**:
- Any user (member, host, or admin) runs: `/warnings`
- Bot performs an immediate read-only check and responds ephemerally to the caller only; no messages are posted to the warnings channel by this command

**Expected Result**:
- Unassigned dates within thresholds trigger warnings (automated daily check)
- Automated warnings posted to configured channel
- Urgent automated warnings ping host and admin roles
- Manual `/warnings` response is ephemeral and visible only to the caller

---

### Scenario 6: Proxy Actions (Host or Admin Assigns Another User)

**Goal**: A host or admin assigns another user to a date on their behalf.

**Setup**:
- Invoking user must hold a Discord role listed in `host_role_ids` or `admin_role_ids` (Configuration sheet)

**Steps**:
1. Host runs: `/volunteer user:@hostuser123 date:2025-11-11` (date chosen from autocomplete dropdown)
2. Bot verifies invoker has host or admin role
3. Bot assigns `@hostuser123` to date
4. Bot sends confirmation

**Expected Result**:
- Host assigned successfully
- Audit log shows invoker as `assigned_by`
- Host receives notification (optional, can be added)

---

### Scenario 7: Cancel Volunteering

**Goal**: Host needs to cancel their commitment.

**Steps**:
1. Host runs: `/unvolunteer user:@self date:2025-11-11` (date chosen from autocomplete dropdown of the user's assigned dates)
2. Bot verifies host is assigned to date
3. Bot removes assignment from Google Sheets
4. Bot triggers immediate warning check
5. Bot sends confirmation

**Expected Result**:
- Assignment removed from Google Sheets
- If date is now within warning threshold, warning posted immediately
- Audit log entry created

---

### Scenario 8: Synchronization (Manual or Automatic)

**Goal**: Sync bot state with Google Sheets after manual edits.

**Automatic Sync**:
- Bot syncs every `cache_ttl_seconds` (default: 5 minutes)
- Bot detects changes and updates cache

**Manual Sync**:
- Admin runs: `/sync`
- Bot forces immediate sync with Google Sheets
- Bot reports sync status

**Expected Result**:
- Bot state matches Google Sheets
- Cache updated with latest data
- Sync status reported: "✅ Sync complete: 45 events, 3 patterns synced"

**Use Cases**:
- Manual edits made to Google Sheets during bot downtime
- Data corruption recovery
- After bulk edits in Google Sheets

---

### Scenario 9: Resilience (API Failure)

**Goal**: Bot continues operating when Google Sheets API is unavailable.

**Flow**:
1. Bot attempts Google Sheets API call
2. API returns error (network issue, quota exceeded, etc.)
3. Bot serves from cache
4. Bot shows staleness warning: "⚠️ Data may be out of date. Last synced: [timestamp]"
5. Bot logs error for monitoring
6. Bot continues serving cached data

**Expected Result**:
- Bot remains functional
- Users see staleness warning
- Write operations disabled until API available
- Bot automatically syncs when API recovers

**Recovery**:
- Bot retries sync automatically
- Admin can force sync via `/sync` command

---

### Scenario 10: Database Reset

**Goal**: Recover from data corruption or inconsistency.

**Steps**:
1. Admin runs: `/reset`
2. Bot shows reset instructions
3. Admin verifies Google Sheets contains correct data
4. Admin runs: `/reset confirm:yes`
5. Bot clears local cache
6. Bot reinitializes from Google Sheets
7. Bot verifies data integrity

**Expected Result**:
- Local cache cleared
- Bot reinitialized from Google Sheets (authoritative source)
- All data integrity checks pass
- Bot returns to normal operation

**Warning**: This should be last resort. Try `/sync` first.

---

## Key Integration Points

### Discord Integration

- **Command Registration**: Bot registers slash commands on startup
- **Command Handling**: Commands handled via discord.py interaction system
- **Permissions**: Three-tier role-based access control (member/host/admin) via Discord role IDs in Configuration sheet
- **Rate Limiting**: discord.py handles Discord API rate limits automatically

### Google Sheets Integration

- **Authentication**: Service account OAuth (unattended operation)
- **Data Sync**: Periodic sync (every 5 minutes) + manual sync via `/sync`
- **Quota Management**: Batching, caching, exponential backoff
- **Resilience**: Cache fallback when API unavailable

### Cache Integration

- **Storage**: Local JSON file (`cache.json`)
- **TTL**: 5 minutes (configurable)
- **Invalidation**: On sync, manual sync, or TTL expiration
- **Format**: JSON structure matching Google Sheets data

---

## Testing Your Setup

### Smoke Tests

1. **Bot Startup**:
   ```bash
   python src/main.py
   ```
   - Bot connects to Discord ✅
   - Bot syncs with Google Sheets ✅
   - Commands registered ✅

2. **Help Command**:
   ```
   /help
   ```
   - Returns list of commands ✅

3. **Volunteer Command**:
   ```
   /volunteer user:@self date:2025-11-11
   ```
   (date selected from autocomplete dropdown)
   - Assigns host to date ✅
   - Updates Google Sheets ✅
   - Sends confirmation ✅

4. **Schedule Command**:
   ```
   /schedule
   ```
   - Shows schedule ✅
   - Response within 3 seconds ✅

5. **Sync Command** (requires admin role):
   ```
   /sync
   ```
   - Syncs with Google Sheets ✅
   - Reports status ✅

---

## Next Steps

- **Full Setup**: See `docs/SETUP.md` for detailed deployment instructions
- **Command Reference**: See `docs/COMMANDS.md` for all commands and examples
- **Troubleshooting**: See `docs/TROUBLESHOOTING.md` for common issues
- **Architecture**: See `docs/ARCHITECTURE.md` for system design

---

## Quick Reference

**Environment Variables**:
- `DISCORD_BOT_TOKEN`: Discord bot token
- `GOOGLE_SHEETS_SPREADSHEET_ID`: Google Sheets document ID
- `GOOGLE_SHEETS_CREDENTIALS_FILE`: Path to service account JSON key

**Key Commands**:
- `/volunteer user:[user] date:[date]`: Volunteer for a date (date via autocomplete)
- `/volunteer recurring user:[user] pattern:[pattern]`: Set up recurring pattern
- `/schedule`: View schedule (default 4 weeks, `weeks:` up to 12)
- `/sync`: Force sync (admin only)
- `/warnings`: Read-only warning check (all users; ephemeral response)

**Performance Targets**:
- Command acknowledgment: < 3 seconds
- Schedule queries: < 3 seconds (12 weeks)
- Sheet updates: < 5 seconds (95th percentile)

