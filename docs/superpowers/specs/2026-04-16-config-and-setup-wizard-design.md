# Config Command & Setup Wizard

## Overview

Replace the current owner-only `/setup` command group (role management only) with two new command groups:

- **`/config`** — Granular subcommands for viewing and changing individual bot settings, with autocomplete and validation.
- **`/setup`** — A guided wizard that walks through all essential configuration step-by-step.

## `/config` Command Group

Owner-only. All responses are ephemeral.

### Subcommand structure

| Command | Parameters | Validation |
|---------|-----------|------------|
| `/config show` | *(none)* | Displays all current config grouped by category |
| `/config warnings passive_days` | `value: int` | 1-30 |
| `/config warnings urgent_days` | `value: int` | 1-14 |
| `/config schedule window_weeks` | `value: int` | 1-12 |
| `/config schedule check_time` | `value: string` | HH:MM 24-hour format |
| `/config schedule check_timezone` | `value: string` | IANA timezone, fuzzy autocomplete |
| `/config channels schedule_channel` | `channel: #channel` | Discord channel picker |
| `/config channels warnings_channel` | `channel: #channel` | Discord channel picker |
| `/config roles add` | `bucket: Choice[admin\|host\|member]`, `role: @Role` | Role exists in guild |
| `/config roles remove` | `bucket: Choice[admin\|host\|member]`, `role: @Role` | Role is in bucket |
| `/config roles clear` | `bucket: Choice[admin\|host\|member]` | *(none)* |

### Autocomplete

- **`check_timezone`**: Fuzzy-match autocomplete handler filtering `zoneinfo.available_timezones()`. Returns up to 25 matches (Discord limit).
- **`bucket`**: Static `app_commands.Choice` list: admin, host, member.
- **Integer params**: Discord enforces int type natively; command validates range and returns ephemeral error on out-of-range.
- **Channel params**: Discord native `discord.TextChannel` type provides the channel picker.

### Behavior

Each subcommand:
1. Validates input (type, range, format).
2. Calls `sheets.update_configuration(key, value, type_)` to persist.
3. Calls `await cache.refresh(force=True)` to reload.
4. Responds with confirmation showing old value -> new value.

On validation failure, responds with an ephemeral error describing the expected format/range.

### `/config show`

Displays an embed with sections:

- **Warnings**: `passive_days`, `urgent_days`
- **Schedule**: `window_weeks`, `check_time`, `check_timezone`
- **Channels**: `schedule_channel` (mention or "not set"), `warnings_channel` (mention or "not set")
- **Roles**: admin roles, host roles, member roles (mentions or "none")

## `/setup` Wizard

Owner-only. Ephemeral. A multi-step guided flow using a persistent embed message with `discord.ui.View` buttons/selects.

### Steps

1. **Roles** — "Let's set up who can do what."
   - Shows current admin/host/member role assignments.
   - `RoleSelect` menus for each bucket.
   - "Skip" button to move on.

2. **Channels** — "Where should I post?"
   - `ChannelSelect` for schedule channel.
   - `ChannelSelect` for warnings channel.
   - "Skip" button for each.

3. **Schedule** — "How should warnings work?"
   - Shows current defaults: `check_time`, `check_timezone`, `warning_passive_days`, `warning_urgent_days`, `schedule_window_weeks`.
   - "Use defaults" button accepts all shown values.
   - "Customize" button walks through each setting with text input modals (`discord.ui.Modal`).

4. **Summary** — "Here's your configuration."
   - Shows all configured values in a final embed.
   - "Looks good!" button to finish.

### Implementation details

- State tracked in-memory on the `View` instance (no DB roundtrips for wizard state).
- 30-minute timeout on the view; after timeout the embed updates to "Setup timed out."
- Re-runnable: running `/setup` again shows current values at each step, so you can change what you want and skip the rest.
- Each step persists immediately via `sheets.update_configuration()` + `cache.refresh(force=True)` — no "save all at end" pattern. If the wizard times out mid-way, whatever was already configured stays.

## Migration

### Removed
- `src/commands/setup.py` — deleted entirely.
- `/setup roles`, `/setup role-add`, `/setup role-remove`, `/setup role-clear` — removed.

### Created
- `src/commands/config_cmd.py` — `/config` command group with all subcommands.
- `src/commands/setup_wizard.py` — `/setup` wizard command.

### Modified
- `src/bot.py` — Remove old setup group registration; register new `/config` group and `/setup` command.

### Unchanged
- `src/models/models.py` — `Configuration` dataclass stays as-is.
- `src/services/sheets_service.py` — `update_configuration()` and `load_configuration()` stay as-is.
- `src/services/cache_service.py` — no changes.

## Settings registry

To avoid duplicating validation logic between `/config` and `/setup`, define a `SETTINGS` registry dict in a shared location (e.g., `src/commands/config_cmd.py` or a small `src/utils/config_meta.py`). Each entry maps a setting key to its metadata:

```python
SETTINGS = {
    "warning_passive_days": {
        "group": "warnings",
        "label": "Passive warning days",
        "type": "integer",
        "config_key": "warning_passive_days",
        "min": 1, "max": 30,
        "description": "Days before an unassigned date to post a passive warning",
    },
    "warning_urgent_days": {
        "group": "warnings",
        "label": "Urgent warning days",
        "type": "integer",
        "config_key": "warning_urgent_days",
        "min": 1, "max": 14,
        "description": "Days before an unassigned date to post an urgent warning",
    },
    "schedule_window_weeks": {
        "group": "schedule",
        "label": "Schedule window (weeks)",
        "type": "integer",
        "config_key": "schedule_window_weeks",
        "min": 1, "max": 12,
        "description": "Default number of weeks shown in /schedule",
    },
    "daily_check_time": {
        "group": "schedule",
        "label": "Daily check time",
        "type": "time",
        "config_key": "daily_check_time",
        "description": "Time of day for the automated warning check (HH:MM, 24-hour)",
    },
    "daily_check_timezone": {
        "group": "schedule",
        "label": "Timezone",
        "type": "timezone",
        "config_key": "daily_check_timezone",
        "description": "IANA timezone for the daily check (e.g. America/Los_Angeles)",
    },
    "schedule_channel_id": {
        "group": "channels",
        "label": "Schedule channel",
        "type": "channel",
        "config_key": "schedule_channel_id",
        "description": "Channel where schedule posts are sent",
    },
    "warnings_channel_id": {
        "group": "channels",
        "label": "Warnings channel",
        "type": "channel",
        "config_key": "warnings_channel_id",
        "description": "Channel where warning posts are sent",
    },
}
```

The wizard and `/config` subcommands both reference this registry for validation, labels, and descriptions.
