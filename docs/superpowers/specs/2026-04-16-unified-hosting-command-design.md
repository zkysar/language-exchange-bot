# Unified `/hosting` Command

## Summary

Consolidate `/volunteer date`, `/volunteer recurring`, `/unvolunteer date`, and `/unvolunteer recurring` into a single `/hosting` command with an `action` choice parameter.

## Command Signature

```
/hosting action:<signup|cancel> [date:<date>] [pattern:<text>] [user:<user>]
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | Choice: `signup`, `cancel` | yes | What to do |
| `date` | string (autocomplete) | no | A specific date |
| `pattern` | string (autocomplete for cancel, free text for signup) | no | Recurring pattern |
| `user` | Discord User | no | Target user, defaults to invoker |

At least one of `date` or `pattern` must be provided. If neither is given, respond with an error.

### Autocomplete Behavior

**`date` autocomplete:**
- When `action=signup`: show unassigned dates in the next 12 weeks (same as current `/volunteer date` autocomplete).
- When `action=cancel`: show the target user's assigned future dates (same as current `/unvolunteer date` autocomplete).

**`pattern` autocomplete:**
- When `action=signup`: no autocomplete — free text input (e.g. `"every 2nd Tuesday"`, `"weekly friday"`).
- When `action=cancel`: show the target user's active recurring pattern descriptions.

## Behavior Matrix

| action | date | pattern | behavior |
|--------|------|---------|----------|
| signup | yes | — | Assign user to that specific date. Fail if already assigned. |
| signup | — | yes | Parse pattern, generate dates for next 3 months, show preview with conflicts, present Confirm/Cancel buttons. On confirm, create `RecurringPattern` and assign available dates. |
| signup | yes | yes | Error: provide either a date or pattern, not both. |
| signup | — | — | Error: provide a date or pattern. |
| cancel | yes | — | Remove user from that date. Trigger warning check if date is in urgent window. |
| cancel | — | yes | Deactivate the matched recurring pattern and clear all its future date assignments. |
| cancel | yes | yes | Error: provide either a date or pattern, not both. |
| cancel | — | — | Error: provide a date or pattern. |

## What Changes

### New file
- `src/commands/hosting.py` — single command implementing all behavior above.

### Modified file
- `src/services/discord_service.py` — register `/hosting` command, remove `/volunteer` and `/unvolunteer` group registrations.

### Removed files
- `src/commands/volunteer.py`
- `src/commands/unvolunteer.py`

### Unchanged
- All underlying logic: `SheetsService`, `CacheService`, `WarningService`, `pattern_parser`, audit logging, `_ConfirmView` pattern (moved into hosting.py).
- Other commands: `/schedule`, `/listdates`, `/sheet`, `/help`, etc.

## Implementation Notes

- The `_ConfirmView` (confirm/cancel buttons for recurring signup) moves into `hosting.py`.
- Permission check (`is_host()`) applies to the whole command.
- The `date` autocomplete function needs to inspect the `action` parameter from the interaction namespace to decide which dates to show (open vs. assigned).
- The `pattern` autocomplete function similarly inspects `action` to decide between no-op (signup) and listing active patterns (cancel).
- Write lock, executor pattern, cache refresh, and audit logging all carry over from the existing implementations unchanged.
