# Discord Host Scheduler Bot

A Discord bot that manages host volunteering for recurring meetups, backed by Google Sheets.

## Setup

1. Install deps: `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in:
   - `DISCORD_BOT_TOKEN`
   - `GOOGLE_SHEETS_SPREADSHEET_ID`
   - `GOOGLE_SHEETS_CREDENTIALS_FILE`
3. Share the spreadsheet with the service account email.
4. Run: `python -m src.bot`

On first run the bot creates the required sheets (Schedule, RecurringPatterns,
AuditLog, Configuration) with default configuration. Edit the Configuration sheet
to set `member_role_ids`, `host_role_ids`, `admin_role_ids` (JSON arrays of
Discord role IDs), and `announcement_channel_id`.

## Commands

- `/schedule [weeks] [date]` — upcoming schedule
- `/listdates [user]` — upcoming dates for a user
- `/warnings` — check unassigned dates (ephemeral)
- `/volunteer date date:[date] [user]` — claim an open date
- `/volunteer recurring pattern:[pattern] [user]` — recurring pattern
- `/unvolunteer date date:[date] [user]` — cancel a date
- `/unvolunteer recurring [user]` — cancel recurring pattern
- `/sync` — (admin) force resync
- `/reset` — (admin) reset cache
- `/help [command]` — help

All dates are interpreted and displayed in `America/Los_Angeles`.
