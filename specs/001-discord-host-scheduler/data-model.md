# Data Model: Discord Host Scheduler Bot

**Date**: 2025-11-04  
**Feature**: 001-discord-host-scheduler

## Overview

The data model defines entities, relationships, validation rules, and state transitions for the Discord Host Scheduler Bot. All data is stored in Google Sheets as the authoritative source, with a local JSON cache for resilience.

---

## Entities

### 1. Host

**Description**: A Discord user who can volunteer to host events.

**Fields**:
- `discord_id` (string, required): Discord user ID (snowflake, e.g., "123456789012345678")
- `discord_username` (string, optional): Discord username for display (e.g., "user#1234")
- `created_at` (datetime, optional): Timestamp when first recorded

**Validation Rules**:
- `discord_id` must be a valid Discord snowflake (numeric string, 17-19 digits)
- `discord_username` must match Discord username format if provided

**Relationships**:
- One-to-many with `EventDate` (a host can be assigned to multiple dates)
- One-to-many with `RecurringPattern` (a host can have multiple recurring patterns)

**State Transitions**: None (static entity)

**Google Sheets Storage**: 
- Sheet: "Hosts" (optional, for reference)
- Columns: `discord_id`, `discord_username`, `created_at`

---

### 2. EventDate

**Description**: A specific calendar date that needs a host, with optional host assignment.

**Fields**:
- `date` (date, required): Calendar date in YYYY-MM-DD format (e.g., "2025-11-11")
- `host_discord_id` (string, nullable): Discord ID of assigned host, null if unassigned
- `recurring_pattern_id` (string, nullable): Reference to recurring pattern if this date was assigned via pattern
- `assigned_at` (datetime, nullable): Timestamp when host was assigned
- `assigned_by` (string, nullable): Discord ID of user who made the assignment (for proxy actions)
- `notes` (string, optional): Optional notes about the event (e.g., "Holiday special")

**Validation Rules**:
- `date` must be a valid future date (cannot be in the past)
- `date` must be in YYYY-MM-DD format
- `host_discord_id` must be valid Discord snowflake if provided
- Only one host per date (enforced by unique constraint on `date`)

**Relationships**:
- Many-to-one with `Host` (via `host_discord_id`)
- Many-to-one with `RecurringPattern` (via `recurring_pattern_id`)

**State Transitions**:
1. **Unassigned → Assigned**: When `/volunteer` command succeeds
   - `host_discord_id` set
   - `assigned_at` set to current timestamp
   - `assigned_by` set to command user
2. **Assigned → Unassigned**: When `/unvolunteer` command succeeds
   - `host_discord_id` cleared
   - `assigned_at` cleared
   - `assigned_by` cleared
3. **Assigned → Assigned (different host)**: Manual override in Google Sheets (admin action)

**Google Sheets Storage**:
- Sheet: "Schedule" (primary data sheet)
- Columns: `date`, `host_discord_id`, `host_username`, `recurring_pattern_id`, `assigned_at`, `assigned_by`, `notes`
- Primary key: `date` (unique constraint)

---

### 3. RecurringPattern

**Description**: A schedule rule defining regular hosting commitments (e.g., "every 2nd Tuesday").

**Fields**:
- `pattern_id` (string, required): Unique identifier (UUID or generated ID)
- `host_discord_id` (string, required): Discord ID of host who owns this pattern
- `pattern_description` (string, required): Human-readable pattern (e.g., "every 2nd Tuesday", "monthly")
- `pattern_rule` (string, required): Machine-readable pattern rule (e.g., `relativedelta(weekday=TU(2))` JSON)
- `start_date` (date, required): First date this pattern applies (YYYY-MM-DD)
- `end_date` (date, nullable): Last date this pattern applies, null for indefinite
- `created_at` (datetime, required): Timestamp when pattern was created
- `is_active` (boolean, required): Whether pattern is currently active (false when cancelled)

**Validation Rules**:
- `pattern_id` must be unique
- `pattern_description` must be parseable into `pattern_rule`
- `start_date` must be valid future date
- `end_date` must be after `start_date` if provided
- `pattern_rule` must be valid JSON representation of dateutil.relativedelta

**Pattern Formats Supported**:
- "every Nth [weekday]" (e.g., "every 2nd Tuesday")
- "monthly" (e.g., "every 1st of month")
- "biweekly" (every 2 weeks)
- Custom relative delta patterns

**Relationships**:
- Many-to-one with `Host` (via `host_discord_id`)
- One-to-many with `EventDate` (pattern can generate multiple dates)

**State Transitions**:
1. **Created → Active**: When `/volunteer recurring` command succeeds
   - `is_active` = true
   - Dates generated and assigned
2. **Active → Inactive**: When `/unvolunteer recurring` command succeeds
   - `is_active` = false
   - Affected dates remain assigned but pattern stops generating new dates
3. **Active → Expired**: When `end_date` is reached
   - `is_active` = false (automatic)

**Google Sheets Storage**:
- Sheet: "RecurringPatterns"
- Columns: `pattern_id`, `host_discord_id`, `host_username`, `pattern_description`, `pattern_rule`, `start_date`, `end_date`, `created_at`, `is_active`

---

### 4. Warning

**Description**: An alert about an unassigned date that needs attention.

**Fields**:
- `warning_id` (string, required): Unique identifier (UUID or generated ID)
- `event_date` (date, required): Date that needs a host (YYYY-MM-DD)
- `severity` (enum, required): "passive" (7+ days away) or "urgent" (3 days away)
- `days_until_event` (integer, required): Number of days until event date
- `posted_at` (datetime, nullable): Timestamp when warning was posted to Discord, null if not yet posted
- `posted_channel_id` (string, nullable): Discord channel ID where warning was posted
- `resolved_at` (datetime, nullable): Timestamp when warning was resolved (date assigned)

**Validation Rules**:
- `severity` must be "passive" or "urgent"
- `days_until_event` must be >= 0
- `event_date` must reference an unassigned `EventDate`

**Relationships**:
- Many-to-one with `EventDate` (warning is about a specific date)

**State Transitions**:
1. **Generated → Posted**: When warning check runs and posts to Discord
   - `posted_at` set
   - `posted_channel_id` set
2. **Posted → Resolved**: When date is assigned via `/volunteer`
   - `resolved_at` set
   - Warning no longer displayed

**Google Sheets Storage**:
- Sheet: "Warnings" (optional, for audit)
- Columns: `warning_id`, `event_date`, `severity`, `days_until_event`, `posted_at`, `posted_channel_id`, `resolved_at`

**Note**: Warnings may be ephemeral (not stored in Sheets) if they're automatically resolved when dates are assigned. Consider storing for audit trail (Principle IV).

---

### 5. AuditEntry

**Description**: A log record of system actions for accountability and debugging.

**Fields**:
- `entry_id` (string, required): Unique identifier (UUID or generated ID)
- `timestamp` (datetime, required): When action occurred
- `action_type` (enum, required): Type of action (see Action Types below)
- `user_discord_id` (string, required): Discord ID of user who initiated action
- `target_user_discord_id` (string, nullable): Discord ID of affected user (for proxy actions)
- `event_date` (date, nullable): Date affected by action (if applicable)
- `recurring_pattern_id` (string, nullable): Pattern affected by action (if applicable)
- `outcome` (enum, required): "success" or "failure"
- `error_message` (string, nullable): Error message if outcome is "failure"
- `metadata` (JSON, optional): Additional context (e.g., command parameters, API response codes)

**Action Types**:
- `VOLUNTEER`: User volunteered for a date
- `UNVOLUNTEER`: User unvolunteered from a date
- `VOLUNTEER_RECURRING`: User set up recurring pattern
- `UNVOLUNTEER_RECURRING`: User cancelled recurring pattern
- `VIEW_SCHEDULE`: User viewed schedule (optional, may not log all views)
- `WARNING_POSTED`: System posted warning about unassigned date
- `SYNC_FORCED`: User forced synchronization with Google Sheets
- `RESET`: Database reset performed (admin action)

**Validation Rules**:
- `timestamp` must be valid datetime
- `action_type` must be valid enum value
- `outcome` must be "success" or "failure"
- `error_message` must be provided if `outcome` is "failure"

**Relationships**:
- Many-to-one with `Host` (via `user_discord_id`)
- Many-to-one with `EventDate` (via `event_date`, if applicable)
- Many-to-one with `RecurringPattern` (via `recurring_pattern_id`, if applicable)

**State Transitions**: None (append-only log)

**Google Sheets Storage**:
- Sheet: "AuditLog"
- Columns: `entry_id`, `timestamp`, `action_type`, `user_discord_id`, `target_user_discord_id`, `event_date`, `recurring_pattern_id`, `outcome`, `error_message`, `metadata`

**Logging Requirements** (Principle IV):
- All state-changing actions MUST create audit entries
- Structured JSON format for automated parsing
- Include request context for debugging

---

### 6. Configuration

**Description**: System settings stored in Google Sheets for easy modification without code changes.

**Fields**:
- `setting_key` (string, required): Configuration parameter name (unique)
- `setting_value` (string, required): Configuration value (may be JSON for complex types)
- `setting_type` (enum, required): "string", "integer", "boolean", "datetime", "json"
- `description` (string, optional): Human-readable description of setting
- `updated_at` (datetime, optional): Last modification timestamp

**Configuration Parameters**:

| Setting Key | Type | Default | Description |
|------------|------|---------|-------------|
| `warning_passive_days` | integer | 7 | Days before event to post passive warning |
| `warning_urgent_days` | integer | 3 | Days before event to post urgent warning |
| `daily_check_time` | datetime | "09:00 PST" | Time of day for daily warning check |
| `schedule_window_weeks` | integer | 8 | Default weeks to show in schedule view |
| `organizer_role_ids` | json | [] | Discord role IDs that can use admin commands |
| `host_privileged_role_ids` | json | [] | Discord role IDs that can volunteer for others |
| `schedule_channel_id` | string | null | Discord channel ID for schedule displays |
| `warnings_channel_id` | string | null | Discord channel ID for warning posts |
| `cache_ttl_seconds` | integer | 300 | Cache TTL for Google Sheets data (5 minutes) |
| `max_batch_size` | integer | 100 | Maximum rows to batch in Google Sheets API calls |

**Validation Rules**:
- `setting_key` must be unique
- `setting_value` must match `setting_type` format
- `warning_passive_days` must be > `warning_urgent_days`
- `daily_check_time` must be valid time format
- `schedule_window_weeks` must be between 1 and 52

**Relationships**: None (singleton configuration)

**Google Sheets Storage**:
- Sheet: "Configuration"
- Columns: `setting_key`, `setting_value`, `setting_type`, `description`, `updated_at`

---

## Data Relationships Diagram

```
Host (1) ──────< (many) EventDate
  │
  │ (1)
  │
  └─────────< (many) RecurringPattern
              │
              │ (1)
              │
              └───> (many) EventDate

EventDate (1) ────< (many) Warning
EventDate (1) ────< (many) AuditEntry

Host (1) ────────< (many) AuditEntry
RecurringPattern (1) ────< (many) AuditEntry
```

---

## Google Sheets Structure

### Sheet: "Schedule" (Primary Data)

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| date | date | Event date (YYYY-MM-DD) | 2025-11-11 |
| host_discord_id | string | Assigned host Discord ID | 123456789012345678 |
| host_username | string | Host username (display) | user#1234 |
| recurring_pattern_id | string | Pattern ID if assigned via pattern | abc-123-def |
| assigned_at | datetime | Assignment timestamp | 2025-11-04T10:30:00Z |
| assigned_by | string | User who made assignment | 987654321098765432 |
| notes | string | Optional event notes | Holiday special |

**Constraints**:
- `date` is unique (primary key)
- `date` must be future date
- `host_discord_id` must be valid Discord ID if provided

### Sheet: "RecurringPatterns"

| Column | Type | Description |
|--------|------|-------------|
| pattern_id | string | Unique pattern identifier |
| host_discord_id | string | Owner Discord ID |
| host_username | string | Owner username (display) |
| pattern_description | string | Human-readable pattern |
| pattern_rule | json | Machine-readable rule (dateutil.relativedelta JSON) |
| start_date | date | First applicable date |
| end_date | date | Last applicable date (nullable) |
| created_at | datetime | Creation timestamp |
| is_active | boolean | Active status |

### Sheet: "AuditLog"

| Column | Type | Description |
|--------|------|-------------|
| entry_id | string | Unique entry identifier |
| timestamp | datetime | Action timestamp |
| action_type | string | Action type enum |
| user_discord_id | string | Initiator Discord ID |
| target_user_discord_id | string | Affected user ID (nullable) |
| event_date | date | Affected date (nullable) |
| recurring_pattern_id | string | Affected pattern (nullable) |
| outcome | string | "success" or "failure" |
| error_message | string | Error details (nullable) |
| metadata | json | Additional context |

### Sheet: "Configuration"

| Column | Type | Description |
|--------|------|-------------|
| setting_key | string | Configuration key (unique) |
| setting_value | string | Configuration value |
| setting_type | string | Value type |
| description | string | Human-readable description |
| updated_at | datetime | Last update timestamp |

---

## Cache Structure

**File**: `cache.json` (local file, not in Google Sheets)

```json
{
  "last_sync": "2025-11-04T12:00:00Z",
  "events": {
    "2025-11-11": {
      "host_discord_id": "123456789012345678",
      "host_username": "user#1234",
      "recurring_pattern_id": null,
      "assigned_at": "2025-11-04T10:30:00Z",
      "assigned_by": "987654321098765432",
      "notes": null
    }
  },
  "recurring_patterns": {
    "abc-123-def": {
      "host_discord_id": "123456789012345678",
      "pattern_description": "every 2nd Tuesday",
      "pattern_rule": {"weekday": [1, 2]},
      "start_date": "2025-11-11",
      "end_date": null,
      "is_active": true
    }
  },
  "quota_usage": {
    "reads": 10,
    "writes": 2,
    "last_reset": "2025-11-04T00:00:00Z"
  },
  "cache_version": "1.0"
}
```

**Cache Invalidation**:
- Cache expires after `cache_ttl_seconds` (default 300 seconds)
- Force sync via `/sync` command invalidates cache
- Manual Google Sheets edits require cache invalidation on next sync

---

## Validation Rules Summary

### Date Validation
- All dates must be in YYYY-MM-DD format
- Event dates must be in the future (cannot assign past dates)
- Recurring pattern dates must be valid (e.g., "5th Wednesday" validated against calendar)

### Discord ID Validation
- All Discord IDs must be valid snowflakes (17-19 digit numeric strings)
- Discord usernames must match format: `username#discriminator` or `username`

### Recurring Pattern Validation
- Pattern descriptions must be parseable into dateutil.relativedelta rules
- Pattern start_date must be in the future
- Pattern end_date must be after start_date if provided

### Conflict Detection
- Only one host per date (enforced by unique constraint on `date` in Schedule sheet)
- Recurring pattern assignment checks for conflicts before committing
- Warning generation only for unassigned dates

---

## Data Integrity Constraints

1. **Referential Integrity**:
   - `EventDate.host_discord_id` must reference valid Discord user (not enforced in Sheets, validated in code)
   - `EventDate.recurring_pattern_id` must reference valid pattern in RecurringPatterns sheet
   - `AuditEntry.event_date` must reference valid date in Schedule sheet

2. **Temporal Constraints**:
   - Event dates cannot be in the past
   - Recurring pattern start_date must be <= end_date
   - Audit entry timestamps must be chronological

3. **Business Rules**:
   - Only one host per date (unique constraint)
   - Warning severity determined by days_until_event vs thresholds
   - Active recurring patterns generate dates on creation

---

## Migration & Initialization

### Initial Setup

1. Create Google Sheets document with required sheets:
   - Schedule (with headers)
   - RecurringPatterns (with headers)
   - AuditLog (with headers)
   - Configuration (with headers and default values)

2. Populate Configuration sheet with default values

3. Bot startup:
   - Load configuration from Configuration sheet
   - Sync Schedule and RecurringPatterns from Sheets
   - Initialize cache from synced data
   - Verify data integrity

### Data Synchronization

- **Regular Sync**: Every `cache_ttl_seconds` (default 5 minutes)
- **Force Sync**: Via `/sync` command
- **Conflict Resolution**: Google Sheets is authoritative; cache conflicts resolved by Sheets data
- **Manual Edits**: Bot detects changes on sync and updates cache

