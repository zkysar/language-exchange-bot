# Sheet UX Improvements Design Spec

**Date**: 2026-04-16
**Goal**: Make the Google Sheet approachable for semi-technical users by hiding complexity, protecting internal data, and adding visual cues — all applied programmatically on bot startup.

---

## Problem

The bot's Google Sheet has 4 tabs (Schedule, RecurringPatterns, AuditLog, Configuration) with internal IDs, machine-readable fields, and no guidance. A semi-technical user opening the sheet sees columns like `recurring_pattern_id` and `assigned_by`, worries about breaking something, and doesn't know what's safe to touch.

## Design Decisions

- **Column naming**: Two-tier header approach. Row 1 keeps internal headers (for `get_all_records()` compatibility), hidden via 1px row height. Row 2 is a visible, frozen display row with friendly names.
- **Protection model**: Schedule stays unprotected for manual edits. RecurringPatterns, AuditLog, Configuration are protected with `warning_only=True`. Instructions tab is fully protected.
- **Idempotent**: All UX setup runs on every bot startup inside `ensure_sheets()`. Safe to re-run — checks for existing state before applying changes.

---

## Feature 1: Hide Internal Tabs

**What**: Hide the RecurringPatterns, AuditLog, and Configuration worksheet tabs from the tab bar.

**How**: Call `worksheet.hide()` on each after creation/verification in `ensure_sheets()`. These sheets still exist and are fully readable/writable by the bot. Users can unhide them via View > Hidden sheets if needed.

**Idempotency**: `hide()` is safe to call on an already-hidden sheet.

---

## Feature 2: Protect Internal Tabs

**What**: Protect RecurringPatterns, AuditLog, and Configuration so users get a warning dialog if they try to edit after unhiding.

**How**: Use `worksheet.add_protected_range()` with `warning_only=True` on each sheet. The bot's service account bypasses protection automatically (it's the sheet owner). Schedule remains unprotected.

**Idempotency**: Check for existing protected ranges before adding. Use `spreadsheet.batch_update()` to list protected ranges, skip if already present for a given sheet.

---

## Feature 3: Instructions Tab

**What**: A human-friendly "Instructions" sheet as the first visible tab explaining what the sheet is, what's safe to edit, and what the bot manages.

**Content** (concise, ~10 lines):

```
Language Exchange Bot - Schedule Sheet

This spreadsheet is managed by the Discord bot. Here's what you need to know:

SCHEDULE TAB (safe to edit):
- Date: Event dates in YYYY-MM-DD format
- Host: The Discord username of the person hosting
- Notes: Any notes about the event (optional)
- Blank host = unassigned date (the bot will send reminders)

WHAT NOT TO DO:
- Don't edit the "Host ID" column — the bot fills this from Discord
- Don't rename or reorder columns
- Don't touch hidden sheets (RecurringPatterns, AuditLog, Configuration)
  unless you know what you're doing

NEED HELP?
- Use /help in Discord for bot commands
- Use /schedule to see upcoming dates
- Use /volunteer to sign up for a date
```

**How**: Check if "Instructions" sheet exists; if not, create via `add_worksheet("Instructions", rows=20, cols=1)`. Write content line-by-line to column A (one line per row, no merging needed). Apply bold formatting to the title row, protect the sheet (`warning_only=False`), reorder to position 0 via `reorder_worksheets()`.

**Idempotency**: Skip creation if "Instructions" sheet already exists. To allow content updates, overwrite A1 on each startup.

---

## Feature 4: Two-Tier Display Headers on Schedule

**What**: Keep internal headers in row 1 (hidden) for bot compatibility. Add a visible display row 2 with friendly column names. Hide internal-only columns entirely.

**Row 1 (hidden, 1px height)**: `date | host_discord_id | host_username | recurring_pattern_id | assigned_at | assigned_by | notes`

**Row 2 (visible, bold, frozen)**: `Date | Host ID | Host | | | | Notes`

**Hidden columns** (width set to 0 via batch_update): D (recurring_pattern_id), E (assigned_at), F (assigned_by). Users see only: Date, Host ID, Host, Notes.

**How**:
- Insert row 2 with display headers if not already present (check if row 2 matches expected display headers)
- Hide row 1: `batch_update` with `updateDimensionProperties` setting row 1 pixel size to 1
- Hide columns D-F: `batch_update` with `updateDimensionProperties` setting column pixel size to 0
- Bold and color row 2 via `worksheet.format()`

**Row offset impact**: Data now starts at row 3 instead of row 2. Methods affected:
- `_find_schedule_row()`: enumeration starts at row 3 (index offset changes from `start=2` to `start=3`)
- `upsert_schedule_row()`: `append_row` still works (appends after last row), but positional updates use the offset from `_find_schedule_row` which is already correct
- `clear_schedule_assignment()`: uses `_find_schedule_row`, no change needed
- `delete_future_pattern_rows()`: iterates `get_all_records()` — the `start=2` offset must change to `start=3`
- `get_all_records()` — gspread uses row 1 as headers by default. With the display row inserted at row 2, we need to pass `head=1` explicitly (which is the default) so it still reads row 1 as headers and skips row 2 as a data row. **However**, the display row will appear as the first "data" record. We filter it out: any row where the date field doesn't parse as a valid date is skipped (this already happens in `load_schedule()` via the `parse_iso_date` try/except).

**Idempotency**: Check if row 2 already contains the display headers before inserting.

---

## Feature 5: Data Validation and Conditional Formatting

**What**: Visual cues on the Schedule tab to guide manual editing and highlight important states.

**Data validation** (via `batch_update` with Sheets API v4 `setDataValidation` requests):
- Column A (date): Date validation — must be a valid date. Applied from row 3 onward.

**Conditional formatting** (via `batch_update` with `addConditionalFormatRule`):
- **Unassigned dates**: If column B (host_discord_id) is empty AND column A has a date, highlight the entire row in light yellow (`#FFF9C4`).
- **Past dates**: If column A date is before today, gray out the entire row (`#F5F5F5`, light gray text).

**How**: Use `spreadsheet.batch_update()` with Sheets API v4 request bodies. These are applied to the Schedule sheet only.

**Idempotency**: Clear existing conditional format rules on the Schedule sheet before re-applying. For data validation, re-applying the same validation is a no-op.

---

## Feature 6: Freeze and Formatting

**What**: Freeze headers and date column on Schedule. Apply clean formatting.

**How**:
- `worksheet.freeze(rows=2, cols=1)` on Schedule — locks the two header rows (hidden internal + visible display) and the date column
- `worksheet.freeze(rows=1)` on Instructions
- Bold + background color on Schedule row 2 (display headers): light blue (`#E3F2FD`)
- Column A width set to 120px (dates), column C width set to 150px (host username), column G width set to 200px (notes)

**Idempotency**: Freeze and format calls are idempotent — re-applying the same values is safe.

---

## Implementation Scope

**New method**: `apply_sheet_ux()` in `SheetsService`, called from `ensure_sheets()` after all sheets are created.

**No existing method changes required.** The display row at row 2 is naturally handled by existing code:
- `_find_schedule_row()` uses `col_values(1)` and skips non-matching values. The display row value "Date" won't match any YYYY-MM-DD target, so indices stay aligned (row 3 in sheet = index 3 in enumeration).
- `delete_future_pattern_rows()` uses `get_all_records()` with `enumerate(rows, start=2)`. The display row becomes the first record at index 2 (which IS sheet row 2). It won't match any `recurring_pattern_id`, so it's skipped. Real data starts at index 3 = sheet row 3.
- `load_schedule()` already skips rows where the date field doesn't parse via `parse_iso_date` try/except.
- `load_patterns()`, `load_configuration()`, `append_audit()` operate on other sheets — unaffected.

**Dependencies**: No new packages. All operations use gspread's existing API + `spreadsheet.batch_update()` for Sheets API v4 requests.

---

## Risks

1. **Existing sheets with data**: If a user already has data in the sheet, inserting the display header row 2 would shift all existing data down by one row. The implementation must detect whether the display row already exists before inserting. Detection: check if row 2 col A value equals "Date" (the display header).
2. **API quota**: The UX setup makes several additional API calls on startup (hide, protect, format, batch_update). These are one-time-per-startup calls and well within quota limits.
3. **Protected range accumulation**: If `add_protected_range()` is called on every startup without checking, it could accumulate duplicate protected ranges. Must check before adding.
4. **Conditional format rule accumulation**: Similarly, clearing and re-adding conditional format rules on each startup avoids stacking duplicates.
