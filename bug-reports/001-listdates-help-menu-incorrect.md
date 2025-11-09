# Bug Report: /listdates Marked as "Coming Soon" But Fully Implemented

**Date:** 2025-11-08
**Severity:** Low (UX/Documentation)

## Issue
The `/listdates` command is fully implemented and registered (`src/bot.py:149`), but the help menu shows it as "coming soon".

## Location
`src/commands/help.py`:
- Line 111: Description says "(coming soon)"
- Line 116: `"status": "coming_soon"`
- Line 186: Listed under "Coming soon" section

## Fix
Remove "coming soon" markers from help.py:
1. Remove "(coming soon)" from description (line 111)
2. Delete `"status": "coming_soon"` (line 116)
3. Move from "Coming soon" section to active commands (line 186)

## Impact
Users don't know the command is available.
