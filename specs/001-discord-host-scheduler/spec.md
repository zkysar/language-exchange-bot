# Feature Specification: Discord Host Scheduler Bot

**Feature Branch**: `001-discord-host-scheduler`
**Created**: 2025-11-04
**Status**: Draft
**Input**: User description: "PRD: Discord Host Scheduler Bot - A bot that manages host volunteering for recurring meetups through Google Sheets backend, with automated reminders and warnings"

## Clarifications

### Session 2025-11-04

- Q: Permission model - who can run which commands? → A: Three-tier role model. The Configuration sheet maps Discord role IDs to tiers (`member_role_ids`, `host_role_ids`, `admin_role_ids`); tier membership is determined by which Discord roles a user holds. **member** (read-only, responses visible only to themselves), **host** (member + write: volunteer/unvolunteer self and others), **admin** (host + sync, sheet operations, reset). Role assignment is performed in Discord itself — the bot does not manage role membership. Role→tier mapping is seeded in the Configuration sheet.
- Q: Concurrent booking conflict resolution - what happens when two hosts try to volunteer for the same date simultaneously? → A: First-wins with immediate error response (second user sees "already assigned" error)
- Q: Timezone handling - how should the system handle timezone differences? → A: All dates interpreted and displayed in `America/Los_Angeles` via zoneinfo (DST handled automatically).
- Q: Ambiguous date parsing - how should the system handle date input formats? → A: No free-form date input; date selection is via Discord slash command autocomplete populated with open (unassigned) dates.
- Q: Google Sheets API rate limit handling - what should happen when rate limit is exceeded? → A: Fail-fast: immediately return error to user, suggest retry later

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Volunteer for Single Event (Priority: P1)

A host wants to volunteer for an upcoming meetup date. They use Discord to claim an available date, and the system immediately confirms their commitment.

**Why this priority**: This is the core value proposition - allowing hosts to easily volunteer. Without this, the bot provides no value.

**Independent Test**: Can be fully tested by having a user claim a date via Discord command and verifying the Google Sheet is updated and confirmation is sent.

**Acceptance Scenarios**:

1. **Given** an available meetup date exists, **When** a host runs `/volunteer user:[user] date:[date]` and selects a date from the autocomplete dropdown, **Then** the system adds the host to that date in Google Sheets and sends a confirmation message
2. **Given** a date is already claimed by another host, **When** a host tries to volunteer for that date, **Then** the system shows who is already scheduled and suggests alternative available dates
3. **Given** the autocomplete dropdown only offers open (unassigned) future dates, **When** a host opens the `date:` picker, **Then** claimed and past dates are not shown as options
4. **Given** no open future dates exist, **When** a host opens the `date:` picker, **Then** the dropdown is empty and the system reports no available dates
5. **Given** two hosts attempt to volunteer for the same available date simultaneously, **When** both requests are processed, **Then** the first request succeeds and the second receives an immediate error message showing who is already assigned

---

### User Story 2 - View Schedule (Priority: P1)

Any community member wants to see who is hosting upcoming meetups. They can view a schedule of confirmed hosts for planning purposes.

**Why this priority**: Equally critical to volunteering - users need to see the schedule to know when meetups are happening and who is hosting.

**Independent Test**: Can be fully tested by populating the Google Sheet with host data and verifying the schedule displays correctly in Discord.

**Acceptance Scenarios**:

1. **Given** multiple hosts are scheduled for upcoming dates, **When** a user runs `/schedule`, **Then** the system displays the next 4 weeks (default) of scheduled hosts
2. **Given** a user wants a different window, **When** they run `/schedule weeks:N`, **Then** the system displays the next N weeks of scheduled hosts (default 4, capped at 12)
3. **Given** a user wants to check a specific date, **When** they run `/schedule date:[date]`, **Then** the system shows who is hosting that date or indicates it's unassigned
4. **Given** some dates have no assigned hosts, **When** viewing the schedule, **Then** those dates are clearly marked as needing volunteers

---

### User Story 3 - Cancel Volunteering (Priority: P2)

A host needs to cancel their hosting commitment due to changed circumstances. They remove themselves from the schedule, triggering warnings if needed.

**Why this priority**: Important for flexibility, but the system can function without it initially (manual edits to Google Sheets can handle cancellations as fallback).

**Independent Test**: Can be fully tested by having a scheduled host remove themselves and verifying sheet updates, confirmation messages, and warning triggers.

**Acceptance Scenarios**:

1. **Given** a host is scheduled for a specific date, **When** they run `/unvolunteer [user] [date]`, **Then** the system removes them from the sheet, confirms the cancellation, and checks if warnings should be triggered
2. **Given** a host tries to unvolunteer for a date they're not scheduled for, **When** they run the command, **Then** the system indicates they are not scheduled for that date
3. **Given** a host cancels within the warning window, **When** the cancellation completes, **Then** the system immediately posts a warning about the now-unassigned date

---

### User Story 4 - Recurring Volunteering (Priority: P2)

A host wants to commit to hosting on a regular schedule (e.g., "every 2nd Tuesday"). They set up a recurring pattern that automatically claims multiple dates.

**Why this priority**: Valuable for regular hosts and reduces coordination overhead, but single-date volunteering provides sufficient MVP functionality.

**Independent Test**: Can be fully tested by setting up a recurring pattern, verifying preview, checking for conflicts, and confirming all dates are added to sheet.

**Acceptance Scenarios**:

1. **Given** a host wants to volunteer regularly, **When** they run `/volunteer recurring [user] [pattern]`, **Then** the system shows a preview of the next 3 months of matching dates
2. **Given** some dates in the recurring pattern are already claimed, **When** the system processes the pattern, **Then** it shows conflicts and asks for confirmation to skip those dates
3. **Given** a host confirms a recurring pattern, **When** the system adds the dates, **Then** all dates are added to Google Sheets with a recurring indicator
4. **Given** a host wants to cancel their recurring commitment, **When** they run `/unvolunteer recurring [user]`, **Then** the system deactivates the pattern AND cascade-deletes all future unassigned Schedule rows that point at that pattern (past rows are kept for audit)

---

### User Story 5 - Warning System (Priority: P3)

The system proactively identifies dates without assigned hosts and alerts the community, with escalating urgency based on how soon the event is.

**Why this priority**: Important for preventing scheduling gaps, but can be handled manually at launch. Users can view the schedule to see gaps.

**Independent Test**: Can be fully tested by configuring warning thresholds, creating unassigned dates at different time horizons, and verifying correct warning messages are posted.

**Acceptance Scenarios**:

1. **Given** an unassigned date is 7+ days away, **When** the daily check runs, **Then** the system posts a passive notice in the schedule channel
2. **Given** an unassigned date is 3 days away, **When** the daily check runs, **Then** the system posts an urgent warning pinging host and admin roles
3. **Given** a host cancels creating a gap, **When** the cancellation completes, **Then** the system immediately runs a warning check for that date
4. **Given** any user (member, host, or admin) wants to check warnings manually, **When** they run `/warnings`, **Then** the system performs an immediate read-only check and reports all dates needing attention as an ephemeral response visible only to the caller

---

### User Story 6 - Data Synchronization (Priority: P3)

When manual edits are made to Google Sheets (e.g., during bot downtime), the bot synchronizes its state when it comes back online, preventing data loss.

**Why this priority**: Critical for reliability but not needed for initial testing. Can be added after core functionality is proven.

**Independent Test**: Can be fully tested by manually editing the Google Sheet, restarting the bot, and verifying it reflects the manual changes.

**Acceptance Scenarios**:

1. **Given** the bot is offline, **When** an admin manually adds a host to a date in Google Sheets, **Then** the bot reflects this change when it comes back online
2. **Given** data has been manually edited, **When** a user runs `/sync`, **Then** the bot forces an immediate synchronization with Google Sheets
3. **Given** the Google Sheets API is temporarily unavailable, **When** the bot attempts to sync, **Then** it uses cached data and logs an error without crashing

---

### User Story 7 - Proxy Actions (Priority: P2)

A host or admin can volunteer or unvolunteer any user on their behalf, enabling administrative control over the schedule.

**Why this priority**: Important for administrative flexibility, but not required for hosts to self-manage their commitments.

**Independent Test**: Can be fully tested by having a host or admin perform actions specifying different users and verifying those users are affected.

**Acceptance Scenarios**:

1. **Given** a host wants to assign another user, **When** they run `/volunteer [other-user] [date]`, **Then** the system assigns that user to the date
2. **Given** a host needs to remove another user, **When** they run `/unvolunteer [other-user] [date]`, **Then** the system removes that user from the date
3. **Given** a host or admin runs `/listdates [other-user]`, **When** the command executes, **Then** the system shows all upcoming dates for the specified user (members can only run `/listdates` for themselves)

---

### User Story 8 - Database Reset/Recovery (Priority: P3)

When the database becomes corrupted or inconsistent, an administrator needs to reset it to a clean state without losing the Google Sheets data structure.

**Why this priority**: Important for operational safety and recovery, but should rarely be needed in normal operation.

**Independent Test**: Can be fully tested by corrupting test data, running the reset procedure, and verifying the system returns to a clean, functional state.

**Acceptance Scenarios**:

1. **Given** the database is corrupted or inconsistent, **When** an admin runs `/reset --help`, **Then** the system provides clear instructions on how to safely reset the database
2. **Given** an admin follows the reset procedure, **When** they confirm the reset action, **Then** the system clears corrupted data, reinitializes from Google Sheets, and confirms successful recovery
3. **Given** a reset is in progress, **When** users try to interact with the bot, **Then** they receive a maintenance message indicating the system is temporarily unavailable
4. **Given** the reset completes successfully, **When** the bot comes back online, **Then** all data from Google Sheets is properly loaded and all commands function normally

---

### Edge Cases

- What happens when a user provides an ambiguous date (e.g., "next Tuesday" vs "2025-11-11")? → **Clarified**: Date free-form input is not accepted; users select from a Discord autocomplete dropdown of open dates only.
- How does the system handle timezone differences between Discord users and Google Sheets? → **Clarified**: All dates interpreted and displayed in `America/Los_Angeles` via zoneinfo (handles DST automatically).
- What happens if two hosts try to volunteer for the same available date simultaneously? → **Clarified**: First-wins behavior; first request succeeds, second receives immediate error showing current assignment
- How does the system handle recurring patterns that result in no valid dates (e.g., "5th Wednesday" in months with only 4 Wednesdays)?
- What happens when the Google Sheets API rate limit is exceeded? → **Clarified**: Fail-fast behavior; immediately return error to user with clear message suggesting retry later; use cached data for read operations when available
- How does the system handle malformed recurring patterns (e.g., "every 2th Tuesday")?
- What happens if a host tries to volunteer for multiple dates at once?
- How does the system handle dates that are already in the past but still in the sheet?
- What happens when the Google Sheet is manually corrupted or has invalid data formats?
- How does the system handle Discord permissions (who can run which commands)? → **Clarified**: Three-tier role-based authorization via Discord role IDs stored in Configuration sheet (`member_role_ids`, `host_role_ids`, `admin_role_ids`). Members get read-only ephemeral responses; hosts add write/proxy actions; admins add sync/reset/sheet ops. Role membership is managed in Discord; the bot does not provide commands to add/remove roles.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept Discord slash commands for volunteering, unvolunteering, viewing schedule, and triggering warnings
- **FR-002**: System MUST store all host scheduling data in a Google Sheets document with columns for date, host identifier, recurring indicator, and metadata
- **FR-003**: System MUST present date selection via a Discord slash command autocomplete picker populated with the next N open (unassigned) dates; users select from the dropdown and free-form date input is not accepted. All dates are interpreted and displayed in `America/Los_Angeles` (handles DST via zoneinfo).
- **FR-004**: System MUST prevent double-booking on a best-effort first-wins basis. This guarantee holds only under single-instance deployment and is enforced by (a) an in-process `asyncio.Lock` that serializes all write operations within a single bot process, and (b) a Sheets-based heartbeat lock in the Configuration sheet that prevents a second bot instance from starting while another is alive. Under these conditions, the first successful assignment wins and subsequent concurrent requests receive an immediate error response.
- **FR-005**: System MUST parse recurring patterns including "every Nth [weekday]", "monthly", and similar natural language patterns
- **FR-006**: System MUST preview recurring pattern dates for the next 3 months before commitment
- **FR-007**: System MUST detect conflicts between recurring patterns and existing scheduled dates
- **FR-008**: System MUST allow hosts to cancel single dates or entire recurring patterns. When `/unvolunteer recurring` runs, the pattern is deactivated (`is_active = FALSE`) AND all future unassigned Schedule rows whose `recurring_pattern_id` matches the pattern are deleted; past rows are retained for audit. After this cascade, `/listdates` and other views never display a recurring indicator for a deactivated pattern.
- **FR-009**: System MUST display upcoming schedule for configurable time window. `/schedule` accepts an optional `weeks` parameter (default 4, maximum 12).
- **FR-010**: System MUST run daily automated checks for unassigned dates at configurable time
- **FR-011**: System MUST post warnings for unassigned dates with severity based on days until event (7+ days: passive, 3 days: urgent)
- **FR-012**: System MUST trigger warning checks immediately after any unvolunteer action
- **FR-013**: ~~System MUST support manual warning checks via `/warnings`.~~ **Removed**: the `/warnings` slash command was intentionally removed (PR #19). Warning information is visible in the daily channel post and via `/schedule`.
- **FR-014**: System MUST allow force synchronization with Google Sheets via command
- **FR-015**: System MUST cache last known state to handle temporary Google Sheets API failures; when rate limit exceeded, fail-fast with immediate error message to user suggesting retry later
- **FR-016**: System MUST provide clear error messages pointing to manual sheet editing when bot is unavailable
- **FR-017**: System MUST support proxy actions where one user can volunteer/unvolunteer others (requires host or admin role as defined in `host_role_ids` / `admin_role_ids` in Configuration). Previously the code incorrectly required admin; this was corrected to require host or higher.
- **FR-018**: System MUST log all actions (volunteer, unvolunteer, warnings) to an audit trail
- **FR-019**: System MUST provide help command listing all available commands with descriptions
- **FR-020**: System MUST provide detailed help for each command when requested
- **FR-021**: System MUST allow configuration of warning thresholds, daily check time, and schedule window via Google Sheets settings tab
- **FR-022**: System MUST provide a `/reset` command that displays instructions for safely resetting the database
- **FR-023**: System MUST support database reset that clears local state and reinitializes from Google Sheets authoritative data
- **FR-024**: System MUST prevent user interactions during database reset operation and display maintenance message
- **FR-025**: System MUST verify data integrity after reset and confirm successful recovery
- **FR-026**: System MUST enforce three-tier role-based authorization by reading Discord role IDs from the Configuration sheet and checking the invoking user's Discord roles at command time:
  - `member_role_ids`: read-only commands (`/schedule`, `/listdates [self]`, `/help`); responses MUST be ephemeral (visible only to the invoking user)
  - `host_role_ids`: all member capabilities plus write actions (`/volunteer`, `/unvolunteer`, proxy actions for other users); host responses are visible in-channel. Note: `/warnings` is read-only and available to all tiers (including members); its response is always ephemeral.
  - `admin_role_ids`: all host capabilities plus technical operations (`/sync`, `/reset`, direct sheet operations)
- **FR-027**: Role→tier mapping MUST be maintained by editing the Configuration sheet directly; the bot does NOT provide commands to add/remove members, hosts, or admins. Role membership itself is managed in Discord via standard role assignment.
- **FR-028**: System MUST render all member-invoked responses as ephemeral Discord messages so that members only see output addressed to themselves; host and admin responses MAY be public
- **FR-029**: System MUST support an optional `meeting_schedule` configuration setting (a recurrence pattern such as `every wednesday` or `every 2nd tuesday`) that describes the days the exchange meets. When set:
  - Single-date signups for non-meeting days MUST be rejected with a message identifying the configured schedule
  - Recurring signup patterns MUST align with the meeting schedule (every date the host's pattern generates in the next 3 months must also be a meeting day); misaligned patterns MUST be rejected before the preview
  - `/schedule` MUST display only meeting days in the default (non-user-filtered) view
  - The warning service MUST skip non-meeting days when generating unassigned-day warnings
  - When unset, every day counts and prior behavior is preserved
  - Malformed `meeting_schedule` values MUST fall back gracefully to "allow any day" rather than block all operations

### Key Entities

- **Host**: A Discord user who can volunteer to host events; identified by Discord username/ID
- **Event Date**: A specific calendar date that needs a host; includes date, assigned host (if any), recurring pattern indicator, and assignment timestamp
- **Recurring Pattern**: A schedule rule defining regular hosting commitments; includes pattern description, affected dates, and associated host
- **Warning**: An alert about an unassigned date; includes date, severity level (passive/urgent), timestamp, and target channel/roles
- **Audit Entry**: A log record of system actions; includes timestamp, action type, user who initiated, affected date/host, and outcome
- **Configuration**: System settings; includes warning thresholds (days), daily check time, default schedule window, designated channels, an optional `meeting_schedule` recurrence describing when the exchange meets, and three role ID lists (`member_role_ids`, `host_role_ids`, `admin_role_ids`) stored in the Configuration sheet for three-tier role-based authorization. The role→tier mapping is seeded and edited directly in the sheet; the bot does not manage it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Hosts can volunteer for a date within 30 seconds from starting the command
- **SC-002**: 95% of volunteer/unvolunteer actions successfully update Google Sheets within 5 seconds
- **SC-003**: Schedule queries return results within 3 seconds for up to 12 weeks of data
- **SC-004**: System identifies and warns about unassigned dates within 24 hours of them becoming unassigned
- **SC-005**: Manual Google Sheets edits are reflected in bot state within 5 minutes or immediately on forced sync
- **SC-006**: System maintains 99% uptime over 30-day period (excluding planned maintenance)
- **SC-007**: 90% of hosts successfully set up recurring patterns on first attempt without assistance
- **SC-008**: Zero data loss events during bot restarts or temporary outages
- **SC-009**: All commands return user-friendly error messages rather than technical errors or crashes
- **SC-010**: Reduce admin time spent on manual schedule coordination by 80% compared to manual tracking

### Assumptions

- Discord workspace has slash command permissions enabled
- Google Sheets API access is available and configured
- Users select dates from a Discord autocomplete dropdown; no free-form date input is accepted
- Organizers have access to Google Sheets for manual fallback
- Meetup events occur on consistent schedule (weekly, bi-weekly, or monthly patterns)
- Only one host is needed per event date
- All dates are interpreted and displayed in `America/Los_Angeles` via zoneinfo (DST handled automatically)
- The bot is deployed as a single instance; concurrency guarantees depend on the Sheets heartbeat lock and in-process `asyncio.Lock`
- Discord roles can be used to distinguish members, hosts, and admins via role IDs in the Configuration sheet
- Google Sheets is the authoritative source of truth for scheduling data

## Technical Details

### Discord Commands

**Member Commands** (read-only; responses are ephemeral — visible only to the invoking user):

- `/schedule` - View upcoming host schedule (default 4 weeks; `weeks` parameter up to 12)
- `/schedule date:[date]` - Check who's hosting on a specific date
- `/schedule weeks:[N]` - Show N weeks of schedule (default 4, max 12)
- `/listdates` - View the invoking member's own upcoming hosting dates (self only)
- `/help` - List all available commands
- `/help [command] [subcommand]` - Get detailed help for a specific command
- `/warnings` - Read-only check of unassigned dates within warning thresholds. Available to all users; response is ephemeral (visible only to the caller) and is not posted to any shared channel.

**Host Commands** (member capabilities plus write access; responses are public in-channel):

- `/volunteer user:[user] date:[date]` - Sign up self or another user to host on a specific date (date selected via autocomplete dropdown of open dates)
- `/volunteer recurring user:[user] pattern:[pattern]` - Set up recurring hosting (e.g., "every 2nd Tuesday", "monthly")
- `/unvolunteer user:[user] date:[date]` - Remove self or another user from a specific date
- `/unvolunteer recurring user:[user]` - Cancel a recurring pattern; deactivates the pattern and cascade-deletes all future unassigned Schedule rows that reference it (past rows retained for audit)
- `/listdates user:[user]` - View upcoming hosting dates for any user

**Admin Commands** (host capabilities plus technical operations):

- `/sync` - Force immediate synchronization with Google Sheets
- `/reset` - Display instructions for safely resetting the database in case of corruption

**Role Management**: Role→tier mapping is edited directly in the Configuration sheet (`member_role_ids`, `host_role_ids`, `admin_role_ids`); Discord role membership is managed in Discord. The bot does not provide commands to add or remove members, hosts, or admins.

### Database Reset Procedure

The `/reset` command provides instructions for recovering from database corruption:

1. **Assessment**: The command first explains what reset does and when it's appropriate to use
2. **Backup**: Instructions to verify Google Sheets contains correct data (it's the source of truth)
3. **Reset Execution**:
   - Stop the bot gracefully
   - Clear local database/cache files
   - Restart the bot (it will reinitialize from Google Sheets)
4. **Verification**: Commands to verify data integrity after reset
5. **Audit Log**: The reset action is logged with timestamp and admin who initiated it

The reset should be a last resort - most issues should be resolvable through `/sync` or manual Google Sheets edits.
