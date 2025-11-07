# Google Sheets Template Setup

## Quick Copy-Paste Template

### Sheet 1: Schedule
Copy these headers into row 1 of a sheet named "Schedule":

```
date	host_discord_id	host_username	recurring_pattern_id	assigned_at	assigned_by	notes
```

### Sheet 2: RecurringPatterns
Copy these headers into row 1 of a sheet named "RecurringPatterns":

```
pattern_id	host_discord_id	host_username	pattern_description	pattern_rule	start_date	end_date	created_at	is_active
```

### Sheet 3: AuditLog
Copy these headers into row 1 of a sheet named "AuditLog":

```
entry_id	timestamp	action_type	user_discord_id	target_user_discord_id	event_date	recurring_pattern_id	outcome	error_message	metadata
```

### Sheet 4: Configuration
Copy these headers AND data into a sheet named "Configuration":

**Headers (Row 1):**
```
setting_key	setting_value	setting_type	description	updated_at
```

**Data (Rows 2-11):**
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

## Steps:

1. Go to https://sheets.google.com
2. Create new spreadsheet
3. Name it "Discord Host Scheduler"
4. Copy the Spreadsheet ID from URL:
   ```
   https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_HERE/edit
   ```
5. Create 4 sheets with exact names: Schedule, RecurringPatterns, AuditLog, Configuration
6. Copy the headers above into each sheet
7. For Configuration sheet, also copy the data rows
