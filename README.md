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

Set `meeting_pattern` (e.g. `every wednesday`, `every 2nd tuesday`) to restrict the
`/hosting signup` date autocomplete to only the days your exchange actually meets.
Leave it blank to allow any date. Configurable via `/setup` Step 3 or `/config`.

## Commands

- `/schedule [weeks] [date] [user]` — upcoming schedule; filter by date or user
- `/warnings` — check unassigned dates (ephemeral)
- `/hosting action:signup date:<date>` — claim an open date
- `/hosting action:signup pattern:<pattern>` — set a recurring pattern (e.g. `every 2nd Tuesday`)
- `/hosting action:cancel date:<date>` — cancel a specific date
- `/hosting action:cancel pattern:<pattern>` — cancel a recurring pattern
- `/config show|set|roles` — (owner) view or change configuration
- `/setup` — (owner) guided setup wizard
- `/sync` — (admin) force resync
- `/help [command]` — help

All dates are interpreted and displayed in `America/Los_Angeles`.
