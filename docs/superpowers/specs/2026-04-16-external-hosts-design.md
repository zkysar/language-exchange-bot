# External Hosts Design

**Date:** 2026-04-16  
**Status:** Approved

## Problem

Some hosts participate in the language exchange but are not on Discord. Currently the bot can only assign dates to Discord users, so these people can't be represented in the schedule.

## Solution Overview

Use the existing `host_username` field to store a plain name for external (non-Discord) hosts, with `host_discord_id` left blank. A single property change to `EventDate.is_assigned` makes this work across the system without any sheet schema changes.

## Data Model

**File:** `src/models/models.py`

Change `EventDate.is_assigned`:

```python
# Before
@property
def is_assigned(self) -> bool:
    return bool(self.host_discord_id)

# After
@property
def is_assigned(self) -> bool:
    return bool(self.host_discord_id or self.host_username)
```

External host rows in the Schedule sheet: `host_discord_id=""`, `host_username="Jane"`. No new columns needed.

**Out of scope:** Recurring patterns for external hosts. The recurring pattern flow is tightly coupled to Discord user objects. External hosts are single-date only.

## Command UX

**File:** `src/commands/hosting.py`

Add an optional `name: str` parameter to `/hosting signup`. Rules:
- `name` and `user` are mutually exclusive — providing both returns an ephemeral error
- `name` with `pattern` is not allowed — external hosts are single-date only
- Requires host or admin role (same as today)
- Confirmation: `Jane (not on Discord) is now hosting on **Wed May 6**.`

Cancel flow is unchanged — it operates on the date row directly and works for both Discord and external hosts.

## Display

**File:** `src/commands/schedule.py`

Add a helper used wherever a host is rendered:

```python
def _host_display(ev: EventDate) -> str:
    if ev.host_discord_id:
        return f"<@{ev.host_discord_id}>"
    return f"{ev.host_username} (not on Discord)"
```

Apply to both the full schedule view and the single-date lookup.

## Warnings

No code change required. External host dates have `is_assigned=True` after the model change, so the warning service naturally treats them as covered and skips sending a warning.

## Files Touched

- `src/models/models.py` — `is_assigned` property
- `src/commands/hosting.py` — `name` parameter, external signup path
- `src/commands/schedule.py` — `_host_display` helper, apply in two render locations
