# Discord API Contracts

**Date**: 2025-11-04  
**Feature**: 001-discord-host-scheduler  
**API Type**: Discord Slash Commands

## Overview

This document defines the Discord slash command interfaces for the Host Scheduler Bot. All commands follow Discord's slash command format and return ephemeral or public responses based on command type.

---

## Command Structure

All commands return Discord interaction responses within 3 seconds (acknowledgment) per Principle XIII (User Experience Standards). Long-running operations may continue asynchronously after acknowledgment.

### Response Format

**Success Response**:
```json
{
  "type": 4,  // CHANNEL_MESSAGE_WITH_SOURCE
  "data": {
    "content": "Success message",
    "embeds": [...],  // Optional rich embeds
    "ephemeral": false  // false for public, true for ephemeral
  }
}
```

**Error Response**:
```json
{
  "type": 4,
  "data": {
    "content": "❌ Error: User-friendly error message",
    "ephemeral": true
  }
}
```

---

## Authorization Tiers

The bot uses a three-tier role model driven by Discord role IDs in the Configuration sheet (`member_role_ids`, `host_role_ids`, `admin_role_ids`). Tier membership is determined by checking the invoking user's Discord roles against these lists at command time. Role assignment is managed in Discord itself — the bot does not provide commands to add or remove members/hosts/admins.

- **member**: read-only access (`/schedule`, `/listdates` for self, `/help`). Responses are ephemeral by default. `/schedule` accepts an optional `public:true` flag to opt into a channel-visible reply.
- **host**: member capabilities plus write actions (`/volunteer`/`/hosting`, `/unvolunteer`, proxy actions targeting other users). Write-action confirmations are public in-channel; read-only commands (including `/schedule` and `/help`) remain ephemeral for hosts unless `public:true` is passed.
- **admin**: host capabilities plus technical operations (`/sync`, `/reset`, sheet operations). Admin commands are ephemeral. The first admin role ID is seeded in the Configuration sheet manually.

Every command description is prefixed with 🤫 (ephemeral / only you see the reply) or 📢 (public / whole channel sees the reply) so visibility is discoverable before invocation. Reply bodies themselves are not decorated — Discord's native "Only you can see this message" indicator already identifies ephemeral replies after the fact.

---

## Commands

### `/volunteer`

**Description**: Sign up to host on a specific date.

**Parameters** (in this order):
- `user` (user, optional): Discord user to volunteer (defaults to command user). Requires host or admin role if specifying another user.
- `date` (string, required): Date selected from a Discord **autocomplete dropdown** populated with the next N open (unassigned) future dates. Free-form date input is not accepted.

**Authorization**:
- Members: NOT authorized to volunteer (read-only tier)
- Hosts / Admins: Can volunteer themselves or any other user

**Success Response**:
- Confirms assignment
- Shows assigned date in `America/Los_Angeles` (DST handled by zoneinfo)
- Displays updated schedule if requested

**Error Cases**:
- Date already assigned (raced between autocomplete population and submit): Shows current host and suggests alternatives
- Authorization failure: Explains required permissions

**Example**:
```
/volunteer user:@user123 date:2025-11-11
→ "Successfully assigned @user123 to host on Tuesday, November 11, 2025 (America/Los_Angeles)"
```

**Contract Test Requirements**:
- Verify autocomplete handler returns only open (unassigned) future dates
- Verify authorization checks work correctly
- Verify conflict detection prevents double-booking under the heartbeat lock
- Verify date display uses `America/Los_Angeles` via zoneinfo

---

### `/volunteer recurring`

**Description**: Set up recurring hosting pattern (e.g., "every 2nd Tuesday").

**Parameters**:
- `user` (user, optional): Discord user (defaults to command user). Requires host or admin role if specifying other user.
- `pattern` (string, required): Recurring pattern description (e.g., "every 2nd Tuesday", "monthly", "biweekly")

**Authorization**: Same as `/volunteer`

**Success Response**:
- Shows preview of next 3 months of matching dates
- Lists any conflicts (dates already assigned)
- Asks for confirmation before committing
- Commits all non-conflicting dates after confirmation

**Error Cases**:
- Invalid pattern: Shows pattern format examples
- No valid dates: Explains why pattern produces no dates
- All dates conflicted: Shows conflicts and suggests alternatives

**Example**:
```
/volunteer recurring user:@user123 pattern:"every 2nd Tuesday"
→ Preview: "This pattern will assign @user123 to:
   - Tuesday, November 11, 2025
   - Tuesday, November 25, 2025
   - Tuesday, December 9, 2025
   ...
   Conflicts: None
   Confirm? (yes/no)"
```

**Contract Test Requirements**:
- Verify pattern parsing generates correct dates
- Verify conflict detection works
- Verify preview shows 3 months
- Verify confirmation flow prevents accidental commits

---

### `/unvolunteer`

**Description**: Remove yourself (or another user) from a specific date.

**Parameters** (in this order):
- `user` (user, optional): Discord user to unvolunteer (defaults to command user). Requires host or admin role if specifying another user.
- `date` (string, required): Date selected from a Discord **autocomplete dropdown** populated with the target user's currently-assigned future dates. Free-form date input is not accepted.

**Authorization**: Same as `/volunteer`

**Success Response**:
- Confirms removal
- Triggers immediate warning check if date is now unassigned
- Shows warning if date was within warning threshold

**Error Cases**:
- User not assigned to date (raced): Shows current assignment
- Authorization failure: Explains required permissions

**Example**:
```
/unvolunteer user:@user123 date:2025-11-11
→ "Removed @user123 from Tuesday, November 11, 2025"
→ [If within warning threshold]: "⚠️ Warning: This date is now unassigned and needs a volunteer!"
```

**Contract Test Requirements**:
- Verify removal updates Google Sheets
- Verify warning check triggers immediately
- Verify warning severity based on days until event

---

### `/unvolunteer recurring`

**Description**: Cancel a recurring hosting pattern.

**Parameters**:
- `user` (user, optional): Discord user (defaults to command user). Requires host or admin role if specifying other user.

**Authorization**: Same as `/volunteer`

**Success Response**:
- Shows all affected future dates
- Asks for confirmation
- On confirmation: deactivates the pattern AND cascade-deletes every future Schedule row whose `recurring_pattern_id` matches (past rows are kept for audit)
- No future dates continue to display a recurring indicator for the deactivated pattern

**Error Cases**:
- No active recurring pattern for user: Lists user's patterns
- Multiple patterns: Shows list and asks which to cancel

**Example**:
```
/unvolunteer recurring user:@user123
→ "This will cancel @user123's recurring pattern 'every 2nd Tuesday' and
   remove the following future assignments (past dates are kept for audit):
   - Tuesday, November 25, 2025
   - Tuesday, December 9, 2025
   ...
   Confirm? (yes/no)"
```

**Contract Test Requirements**:
- Verify pattern deactivation (`is_active = FALSE`)
- Verify cascade deletion of future Schedule rows referencing the pattern
- Verify past Schedule rows are retained
- Verify confirmation flow

---

### `/listdates`

**Description**: View all upcoming hosting dates for a user.

**Parameters**:
- `user` (user, optional): Discord user (defaults to command user)

**Authorization**:
- Members: Can only run `/listdates` for themselves (no `user` parameter or `user` = self); responses are ephemeral
- Hosts / Admins: Can view any user's dates; responses are ephemeral by default

**Success Response**:
- Lists all assigned dates for user (next 12 weeks)
- Shows recurring pattern indicator if applicable
- Formatted as embed or table

**Error Cases**:
- Invalid user: Shows user lookup error

**Example**:
```
/listdates user:@user123
→ Embed showing:
   "Upcoming hosting dates for @user123:
   - Tuesday, November 11, 2025 (one-time)
   - Tuesday, November 25, 2025 (recurring: every 2nd Tuesday)
   ..."
```

**Contract Test Requirements**:
- Verify date listing filters correctly
- Verify recurring pattern indicators

---

### `/schedule`

**Description**: View upcoming host schedule.

**Parameters**:
- `date` (string, optional): Specific date to check (defaults to showing the configured schedule window)
- `weeks` (integer, optional): Number of weeks to show. Default is **4**; maximum is **12**.
- `user` (user, optional): Filter to a specific user's dates (members may only filter to themselves).
- `public` (boolean, optional): If `true`, post the reply in-channel (📢). Defaults to `false` (🤫, ephemeral).

**Authorization**:
- Members / Hosts / Admins: Authorized. Reply is ephemeral by default for all tiers; `public:true` opts into a channel-visible reply.

**Success Response**:
- Shows schedule table with dates and assigned hosts
- Marks unassigned dates clearly
- Formatted as embed or table

**Error Cases**:
- Invalid date format: Shows format examples
- Invalid weeks parameter: Shows valid range

**Example**:
```
/schedule weeks:8
→ Embed showing:
   "Host Schedule (next 8 weeks):
   Nov 11: @user123 ✅
   Nov 18: [Unassigned] ⚠️
   Nov 25: @user456 ✅
   ..."
```

**Contract Test Requirements**:
- Verify schedule queries return within 3 seconds for 12 weeks
- Verify `America/Los_Angeles` timezone conversion via zoneinfo
- Verify unassigned date marking

---

### `/help`

**Description**: Show help text for commands.

**Parameters**:
- `command` (string, optional): Specific command name (shows detailed help)

**Authorization**: All tiers (member/host/admin) can view help; responses are ephemeral for everyone

**Success Response**:
- Lists all commands with brief descriptions (if no command specified)
- Shows detailed help for specific command (if command specified)
- Includes examples and parameter descriptions

**Example**:
```
/help command:volunteer
→ "**/volunteer** - Sign up to host on a specific date
   Parameters:
   - user: Discord user (optional, defaults to you)
   - date: Selected from the autocomplete dropdown of open dates
   Examples:
   /volunteer user:@self date:2025-11-11
   /volunteer user:@user123 date:2025-11-18"
```

**Contract Test Requirements**:
- Verify help text exists for all commands
- Verify examples are accurate

---

### `/warnings`

**Description**: Read-only manual check of unassigned dates within warning thresholds.

**Parameters**: None

**Authorization**: Available to **all users** (member, host, admin). No role restriction.

**Response**: Ephemeral — visible only to the invoking user. This command does NOT post to any shared channel; it only reports to the caller. (Scheduled automated warnings still post to the configured warnings channel — that is a separate path.)

**Success Response**:
- Lists all unassigned dates within warning thresholds in an ephemeral reply
- Reports "No warnings" if all dates assigned

**Error Cases**:
- API failure: Shows error and suggests retry

**Example**:
```
/warnings
→ (ephemeral) "Warning Check Results:
   Urgent (3 days):
   - Tuesday, November 7, 2025
   Passive (7+ days):
   - Tuesday, November 11, 2025"
```

**Contract Test Requirements**:
- Verify command is callable without any role check
- Verify response is ephemeral (`ephemeral=True`)
- Verify no message is posted to any shared channel by this command
- Verify warning generation logic (read-only)

---

## Administrative Commands

### `/sync`

**Description**: Force immediate synchronization with Google Sheets.

**Parameters**: None

**Authorization**: Requires admin role (Discord role in `admin_role_ids`)

**Success Response**:
- Confirms sync started
- Shows sync status (success/failure)
- Reports number of records synced
- Shows any conflicts resolved

**Error Cases**:
- Authorization failure: Explains required admin role
- Google Sheets API failure: Shows error and suggests retry
- Quota exceeded: Shows quota status and suggests retry later

**Example**:
```
/sync
→ "🔄 Syncing with Google Sheets...
   ✅ Sync complete: 45 events, 3 patterns synced
   Cache updated."
```

**Contract Test Requirements**:
- Verify Google Sheets API integration
- Verify cache invalidation
- Verify quota handling

---

### `/reset`

**Description**: Display instructions for safely resetting the database.

**Parameters**: None

**Authorization**: Requires admin role (Discord role in `admin_role_ids`)

**Success Response**:
- Shows reset procedure instructions
- Explains what reset does
- Provides step-by-step guide
- Requires additional confirmation before actual reset

**Note**: This command shows instructions only. Actual reset requires additional confirmation or separate command.

**Example**:
```
/reset
→ "**Database Reset Instructions**
   
   This command provides instructions for resetting the bot's local database
   in case of corruption or data inconsistency.
   
   **What reset does:**
   - Clears local cache file
   - Reinitializes from Google Sheets (authoritative source)
   - Preserves Google Sheets data
   
   **Steps:**
   1. Verify Google Sheets contains correct data
   2. Stop the bot gracefully
   3. Delete cache.json file
   4. Restart the bot
   
   **To execute reset:** /reset confirm:yes"
```

**Contract Test Requirements**:
- Verify instructions are clear
- Verify reset confirmation flow
- Verify data integrity after reset

---

## Rate Limiting

Discord API rate limits:
- **Global Rate Limit**: 50 requests per second per bot
- **Per-Route Rate Limit**: Varies by endpoint (slash commands typically 5/second)

**Implementation**:
- discord.py handles rate limiting automatically
- Exponential backoff on 429 responses
- Log rate limit events for monitoring

**Contract Test Requirements**:
- Verify rate limit handling
- Verify 429 response handling
- Verify exponential backoff

---

## Error Handling

All commands must handle:
- **Invalid Parameters**: Return user-friendly error with examples
- **Authorization Failures**: Explain required permissions
- **API Failures**: Show friendly message, log technical details
- **Rate Limits**: Show "Please try again in a moment" message
- **Timeout**: Acknowledge within 3s, continue processing async

**Error Message Format**:
```
❌ Error: [User-friendly description]
[How to fix, if applicable]
```

**Contract Test Requirements**:
- Verify error messages are user-friendly (no stack traces)
- Verify technical errors are logged but not shown to users
- Verify timeout handling

---

## Testing Requirements

### Contract Tests

Contract tests MUST verify:
1. Command registration: All commands registered with Discord
2. Parameter validation: Commands reject invalid parameters correctly
3. Authorization: Commands enforce role-based access
4. Response format: Commands return correct Discord interaction format
5. Rate limiting: Commands handle rate limits gracefully
6. Error handling: Commands return user-friendly errors

### Integration Tests

Integration tests MUST verify:
1. End-to-end flows: Complete user journeys (volunteer → sheet update → confirmation)
2. Discord API integration: Real Discord API calls (test server)
3. Google Sheets integration: Real Google Sheets API calls (test sheet)
4. Cache behavior: Cache hits, misses, staleness handling

### Mock Requirements

- Mock Discord API responses for unit tests
- Mock Google Sheets API responses for unit tests
- Use real APIs only in integration/contract tests

