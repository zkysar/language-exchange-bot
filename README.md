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

Set `meeting_schedule` (e.g. `every wednesday`, `every 2nd tuesday`) to describe
when the exchange meets. When set, it restricts `/hosting` signups (single dates
and recurring patterns), hides non-meeting days in `/schedule`, and keeps warnings
focused on meeting days. Leave it blank to allow any date. Configurable via
`/setup` Step 3 or `/config action:set key:meeting_schedule value:...` (empty
value clears it).

The bot posts two kinds of announcements to `announcement_channel_id`:

- **Warnings**: `warning_passive_days` / `warning_urgent_days` fire at
  `daily_check_time` once per day for unassigned upcoming dates.
- **Schedule announcement**: every `schedule_announcement_interval_days` days
  (state tracked in `last_schedule_announcement_at`) the bot posts a
  `schedule_announcement_lookahead_weeks`-wide upcoming-schedule roster.

For any of these four integer settings, an **empty value disables that
announcement** — clear the cell in the Configuration sheet or run
`/config action:set key:<name> value:` with no value.

## Commands

Every command description is prefixed with 🤫 (reply private to you) or 📢
(reply visible to the whole channel) so you know up front which way a command
will post.

- `/schedule [weeks] [date] [user] [public]` — 🤫 upcoming schedule; pass
  `public:true` to share the reply with the channel (📢)
- `/hosting action:signup date:<date>` — 📢 claim an open date
- `/hosting action:signup pattern:<pattern>` — 📢 set a recurring pattern (e.g. `every 2nd Tuesday`)
- `/hosting action:cancel date:<date>` — 📢 cancel a specific date
- `/hosting action:cancel pattern:<pattern>` — 📢 cancel a recurring pattern
- `/config show|set|roles` — 🤫 (owner) view or change configuration
- `/setup` — 🤫 (owner) guided setup wizard
- `/sync` — 🤫 (admin) force resync
- `/help [command]` — 🤫 help

All dates are interpreted and displayed in `America/Los_Angeles`.
