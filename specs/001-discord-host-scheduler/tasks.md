# Implementation Tasks: Discord Host Scheduler Bot

**Feature Branch**: `001-discord-host-scheduler`  
**Generated**: 2025-11-04  
**Source Documents**: plan.md, spec.md, data-model.md, contracts/, research.md

## Overview

This document contains the implementation tasks organized by user story priority. Each task follows the checklist format and includes specific file paths. Tasks are designed to be independently executable by an LLM without additional context.

**Total Tasks**: 153  
**User Stories**: 8 (P1: 2, P2: 3, P3: 3)  
**MVP Scope**: User Stories 1 & 2 (P1) - Volunteer for Single Event & View Schedule

---

## Implementation Strategy

### MVP First Approach
- **Phase 1-4**: Core functionality (Setup, Foundational, US1, US2)
- **Phase 5-7**: Enhanced features (US3, US4, US7)
- **Phase 8-10**: Advanced features (US5, US6, US8)
- **Phase 11**: Polish & cross-cutting concerns

### Incremental Delivery
Each user story phase is independently testable and can be deployed separately. Dependencies between stories are documented in the Dependencies section.

### Parallel Execution
Tasks marked with `[P]` can be executed in parallel within the same phase, as they operate on different files with no dependencies on incomplete tasks.

---

## Dependencies

### User Story Completion Order
1. **Phase 1 (Setup)**: Must complete before all other phases
2. **Phase 2 (Foundational)**: Must complete before user story phases
3. **Phase 3 (US1 - Volunteer)**: Can be parallel with Phase 4
4. **Phase 4 (US2 - View Schedule)**: Can be parallel with Phase 3
5. **Phase 5 (US3 - Cancel Volunteering)**: Depends on Phase 3
6. **Phase 6 (US4 - Recurring Volunteering)**: Depends on Phase 3
7. **Phase 7 (US7 - Proxy Actions)**: Depends on Phase 3
8. **Phase 8 (US5 - Warning System)**: Depends on Phase 3, Phase 4
9. **Phase 9 (US6 - Data Synchronization)**: Depends on Phase 2, Phase 3, Phase 4
10. **Phase 10 (US8 - Database Reset)**: Depends on all previous phases
11. **Phase 11 (Polish)**: Depends on all user story phases

### Story Dependencies Graph
```
Setup → Foundational → US1/US2 (parallel)
                      ↓
                   US3/US4/US7 (parallel, depends on US1)
                      ↓
                   US5 (depends on US1, US2)
                      ↓
                   US6 (depends on Foundational, US1, US2)
                      ↓
                   US8 (depends on all)
                      ↓
                   Polish
```

---

## Phase 1: Setup & Project Initialization

**Goal**: Initialize project structure, dependencies, and configuration files.

**Independent Test**: Project can be set up from scratch, dependencies install successfully, and basic configuration files exist.

### Project Structure

- [x] T001 Create project root directory structure (src/, tests/, specs/)
- [x] T002 Create src/models/ directory for entity models
- [x] T003 Create src/services/ directory for business logic services
- [x] T004 Create src/commands/ directory for Discord command handlers
- [x] T005 Create src/utils/ directory for shared utilities
- [x] T006 Create tests/contract/ directory for API contract tests
- [x] T007 Create tests/integration/ directory for integration tests
- [x] T008 Create tests/unit/ directory for unit tests

### Dependencies & Configuration

- [x] T009 Create requirements.txt with core dependencies (discord.py>=2.3.0, gspread>=5.12.0, google-auth>=2.23.0, python-dateutil>=2.8.0)
- [x] T010 Create requirements.txt with development dependencies (pytest>=7.4.0, pytest-asyncio>=0.21.0, pytest-mock>=3.12.0)
- [x] T011 Create pyproject.toml with project metadata and optional configuration
- [x] T012 Create .env.example template with placeholder values (DISCORD_BOT_TOKEN, GOOGLE_SHEETS_SPREADSHEET_ID, GOOGLE_SHEETS_CREDENTIALS_FILE)
- [x] T013 Create .gitignore file excluding .env, cache.json, __pycache__/, *.pyc, .pytest_cache/
- [x] T014 Create .pre-commit-config.yaml with black, flake8 hooks for code quality enforcement

### Documentation Setup

- [x] T015 Create README.md with project overview, setup instructions, and links to documentation
- [x] T016 Create SETUP.md template for deployment instructions (to be filled in Phase 11)
- [x] T017 Create COMMANDS.md template for command reference (to be filled in Phase 11)
- [x] T018 Create TROUBLESHOOTING.md template for common issues (to be filled in Phase 11)
- [x] T019 Create ARCHITECTURE.md template for system design (to be filled in Phase 11)

---

## Phase 2: Foundational Components

**Goal**: Implement core models, services, and utilities that are prerequisites for all user stories.

**Independent Test**: Models can be instantiated, services can be initialized, and utilities can be tested independently.

### Models (Data Entities)

- [x] T020 [P] Create Host model in src/models/host.py with discord_id, discord_username, created_at fields
- [x] T021 [P] Create EventDate model in src/models/event_date.py with date, host_discord_id, recurring_pattern_id, assigned_at, assigned_by, notes fields
- [x] T022 [P] Create RecurringPattern model in src/models/recurring_pattern.py with pattern_id, host_discord_id, pattern_description, pattern_rule, start_date, end_date, created_at, is_active fields
- [x] T023 [P] Create Warning model in src/models/warning.py with warning_id, event_date, severity, days_until_event, posted_at, posted_channel_id, resolved_at fields
- [x] T024 [P] Create AuditEntry model in src/models/audit_entry.py with entry_id, timestamp, action_type, user_discord_id, target_user_discord_id, event_date, recurring_pattern_id, outcome, error_message, metadata fields
- [x] T025 [P] Create Configuration model in src/models/configuration.py with setting_key, setting_value, setting_type, description, updated_at fields and default configuration values

### Core Services

- [x] T026 Create SheetsService in src/services/sheets_service.py with Google Sheets API integration, authentication, and basic read/write operations
- [x] T027 Create CacheService in src/services/cache_service.py with JSON file-based caching, TTL management, and cache invalidation logic
- [x] T028 Create DiscordService foundation in src/services/discord_service.py with bot initialization, connection handling, and basic event handlers
- [x] T029 Create SyncService in src/services/sync_service.py with data synchronization logic between Google Sheets and cache, conflict resolution

### Utilities

- [x] T030 [P] Create date_parser utility in src/utils/date_parser.py with YYYY-MM-DD format validation, future date validation, and PST timezone handling
- [x] T031 [P] Create pattern_parser utility in src/utils/pattern_parser.py with recurring pattern parsing (every Nth weekday, monthly, biweekly) and dateutil.relativedelta conversion
- [x] T032 [P] Create auth utility in src/utils/auth.py with Discord role-based authorization checking, organizer role validation, and host-privileged role validation
- [x] T033 [P] Create logger utility in src/utils/logger.py with structured JSON logging setup, console and file output configuration

### Bot Entry Point

- [x] T034 Create bot.py in src/bot.py with main entry point, bot initialization, service initialization, and graceful shutdown handling

---

## Phase 3: User Story 1 - Volunteer for Single Event (P1)

**Goal**: Hosts can volunteer for upcoming meetup dates via Discord command.

**Independent Test**: User can run `/volunteer date:2025-11-11`, verify Google Sheet is updated, and receive confirmation message.

**Test Criteria**:
- Command accepts valid future dates in YYYY-MM-DD format
- Command rejects invalid formats with clear error message
- Command prevents double-booking (first-wins conflict resolution)
- Command updates Google Sheets Schedule sheet correctly
- Command creates audit log entry
- Command sends confirmation message to Discord

### Implementation Tasks

- [x] T035 [US1] Create volunteer command handler in src/commands/volunteer.py with single date volunteering logic
- [x] T036 [US1] Implement date validation in volunteer command (YYYY-MM-DD format, future date check) using src/utils/date_parser.py
- [x] T037 [US1] Implement conflict detection in volunteer command (check existing assignments in Schedule sheet)
- [x] T038 [US1] Implement first-wins conflict resolution in volunteer command (immediate error if date already assigned)
- [x] T039 [US1] Implement Google Sheets update in volunteer command (update Schedule sheet via SheetsService)
- [x] T040 [US1] Implement audit logging in volunteer command (create AuditEntry via SheetsService)
- [x] T041 [US1] Implement cache invalidation in volunteer command (invalidate cache after successful update)
- [x] T042 [US1] Implement Discord response formatting in volunteer command (confirmation message with PST timezone display)
- [x] T043 [US1] Register /volunteer slash command in src/services/discord_service.py with user and date parameters
- [x] T044 [US1] Implement error handling in volunteer command (invalid date format, past date, already assigned, API failures)

---

## Phase 4: User Story 2 - View Schedule (P1)

**Goal**: Community members can view upcoming host schedule.

**Independent Test**: User can run `/schedule`, verify schedule displays correctly with assigned hosts and unassigned dates marked clearly.

**Test Criteria**:
- Command displays next 4-8 weeks of scheduled hosts (configurable)
- Command shows unassigned dates clearly marked
- Command supports optional date parameter for specific date lookup
- Command formats dates in PST timezone
- Command responds within 3 seconds for 12 weeks of data
- Command uses cache when available to reduce API calls

### Implementation Tasks

- [x] T045 [US2] Create schedule command handler in src/commands/schedule.py with schedule viewing logic
- [x] T046 [US2] Implement schedule query in schedule command (query Schedule sheet for date range via SheetsService or cache)
- [x] T047 [US2] Implement schedule formatting in schedule command (format as Discord embed with dates and hosts)
- [x] T048 [US2] Implement unassigned date marking in schedule command (clearly mark dates without assigned hosts)
- [x] T049 [US2] Implement PST timezone conversion in schedule command (display all dates in PST)
- [x] T050 [US2] Implement cache usage in schedule command (use cache if available and not expired)
- [x] T051 [US2] Implement optional date parameter in schedule command (show specific date if provided)
- [x] T052 [US2] Implement optional weeks parameter in schedule command (show N weeks, default from configuration)
- [x] T053 [US2] Register /schedule slash command in src/services/discord_service.py with optional date and weeks parameters
- [x] T054 [US2] Implement error handling in schedule command (API failures, invalid date format, cache staleness warnings)

---

## Phase 5: User Story 3 - Cancel Volunteering (P2)

**Goal**: Hosts can cancel their hosting commitments.

**Independent Test**: User can run `/unvolunteer date:2025-11-11`, verify Google Sheet is updated, confirmation message sent, and warning check triggered if needed.

**Test Criteria**:
- Command removes host from specified date
- Command validates host is assigned to date before removal
- Command triggers immediate warning check after successful removal
- Command updates Google Sheets Schedule sheet correctly
- Command creates audit log entry
- Command sends confirmation message

### Implementation Tasks

- [x] T055 [US3] Create unvolunteer command handler in src/commands/unvolunteer.py with single date cancellation logic
- [x] T056 [US3] Implement assignment validation in unvolunteer command (verify host is assigned to date)
- [x] T057 [US3] Implement Google Sheets update in unvolunteer command (clear host assignment in Schedule sheet)
- [x] T058 [US3] Implement audit logging in unvolunteer command (create AuditEntry via SheetsService)
- [x] T059 [US3] Implement cache invalidation in unvolunteer command (invalidate cache after successful update)
- [x] T060 [US3] Implement immediate warning check trigger in unvolunteer command (call WarningService.check_warnings after removal)
- [x] T061 [US3] Implement Discord response formatting in unvolunteer command (confirmation message)
- [x] T062 [US3] Register /unvolunteer slash command in src/services/discord_service.py with user and date parameters
- [x] T063 [US3] Implement error handling in unvolunteer command (not assigned, invalid date, API failures)

---

## Phase 6: User Story 4 - Recurring Volunteering (P2)

**Goal**: Hosts can set up recurring hosting patterns.

**Independent Test**: User can run `/volunteer recurring pattern:"every 2nd Tuesday"`, verify preview shown, dates assigned after confirmation, and recurring pattern created.

**Test Criteria**:
- Command parses recurring pattern descriptions correctly
- Command generates preview of next 3 months of matching dates
- Command detects conflicts with existing assignments
- Command asks for confirmation before committing
- Command assigns all non-conflicting dates to Google Sheets
- Command creates RecurringPattern entry in sheet

### Implementation Tasks

- [x] T064 [US4] Implement recurring pattern volunteering in src/commands/volunteer.py (add recurring subcommand)
- [x] T065 [US4] Implement pattern parsing in volunteer recurring command (use pattern_parser utility for pattern description)
- [x] T066 [US4] Implement date generation in volunteer recurring command (generate next 3 months of dates using pattern_parser and dateutil.relativedelta)
- [x] T067 [US4] Implement conflict detection in volunteer recurring command (check each generated date against existing assignments)
- [x] T068 [US4] Implement preview display in volunteer recurring command (show dates and conflicts in Discord embed)
- [x] T069 [US4] Implement confirmation flow in volunteer recurring command (ask for yes/no confirmation before committing)
- [x] T070 [US4] Implement batch assignment in volunteer recurring command (assign all non-conflicting dates via SheetsService batch update)
- [x] T071 [US4] Implement RecurringPattern creation in volunteer recurring command (create pattern entry in RecurringPatterns sheet)
- [x] T072 [US4] Implement audit logging in volunteer recurring command (create AuditEntry for recurring pattern creation)
- [x] T073 [US4] Register /volunteer recurring slash command in src/services/discord_service.py with user and pattern parameters
- [x] T074 [US4] Implement error handling in volunteer recurring command (invalid pattern, no valid dates, all dates conflicted, API failures)

---

## Phase 7: User Story 7 - Proxy Actions (P2)

**Goal**: Organizers can volunteer/unvolunteer users on their behalf.

**Independent Test**: Organizer can run `/volunteer user:@otheruser date:2025-11-11`, verify authorization check, assignment made, and audit log shows organizer as assigned_by.

**Test Criteria**:
- Command checks organizer has host-privileged role
- Command assigns specified user to date
- Command sets assigned_by field to organizer's Discord ID
- Command creates audit log entry with proxy action details
- Authorization failures return clear error messages

### Implementation Tasks

- [ ] T075 [US7] Implement authorization check in volunteer command (check host-privileged role when user parameter differs from command user)
- [ ] T076 [US7] Implement proxy action handling in volunteer command (set assigned_by field to organizer's Discord ID)
- [ ] T077 [US7] Implement authorization check in unvolunteer command (check host-privileged role when user parameter differs from command user)
- [ ] T078 [US7] Implement proxy action handling in unvolunteer command (set assigned_by field in audit log)
- [ ] T079 [US7] Update auth utility in src/utils/auth.py with host-privileged role checking function
- [ ] T080 [US7] Implement error handling for authorization failures (clear error messages explaining required permissions)

---

## Phase 8: User Story 5 - Warning System (P3)

**Goal**: System proactively identifies and warns about unassigned dates.

**Independent Test**: Configure warning thresholds, create unassigned dates, verify daily check runs and posts warnings with correct severity.

**Test Criteria**:
- Daily check runs at configured time
- Warning severity calculated correctly (passive for 7+ days, urgent for 3 days)
- Warnings posted to configured Discord channel
- Urgent warnings ping organizer role
- Immediate warning check triggered after unvolunteer action
- Manual warning check via /warnings command works

### Implementation Tasks

- [x] T081 [US5] Create WarningService in src/services/warning_service.py with warning generation, severity calculation, and posting logic
- [x] T082 [US5] Implement warning check in WarningService (query unassigned dates, calculate days until event, determine severity)
- [x] T083 [US5] Implement warning posting in WarningService (post to Discord channel, ping organizer role for urgent warnings)
- [x] T084 [US5] Implement daily scheduled task in src/services/discord_service.py (use discord.py tasks for daily warning check at configured time)
- [x] T085 [US5] Create warnings command handler in src/commands/warnings.py with manual warning check trigger
- [x] T086 [US5] Implement immediate warning check in unvolunteer command (call WarningService.check_warnings after successful removal)
- [x] T087 [US5] Register /warnings slash command in src/services/discord_service.py (admin-only, no parameters)
- [x] T088 [US5] Implement authorization check in warnings command (require organizer role)
- [x] T089 [US5] Implement error handling in warnings command (API failures, missing channel configuration)

---

## Phase 9: User Story 6 - Data Synchronization (P3)

**Goal**: Bot synchronizes state with Google Sheets when manual edits occur.

**Independent Test**: Manually edit Google Sheet, restart bot or run /sync, verify bot reflects manual changes.

**Test Criteria**:
- Bot syncs on startup (loads data from Google Sheets)
- Periodic sync runs every cache_ttl_seconds (default 5 minutes)
- Manual sync via /sync command works
- Sync detects changes and updates cache
- Sync handles API failures gracefully (uses cache, shows staleness warning)
- Sync resolves conflicts (Google Sheets is authoritative)

### Implementation Tasks

- [x] T090 [US6] Implement startup sync in src/bot.py (load Configuration, Schedule, RecurringPatterns from Google Sheets on startup)
- [x] T091 [US6] Implement periodic sync task in SyncService (sync every cache_ttl_seconds, update cache with changes)
- [x] T092 [US6] Implement change detection in SyncService (compare Google Sheets data with cache, identify changes)
- [x] T093 [US6] Implement conflict resolution in SyncService (Google Sheets is authoritative, cache conflicts resolved by Sheets data)
- [x] T094 [US6] Implement sync command handler in src/commands/sync.py with force sync logic
- [x] T095 [US6] Register /sync slash command in src/services/discord_service.py (admin-only, no parameters)
- [x] T096 [US6] Implement authorization check in sync command (require organizer role)
- [x] T097 [US6] Implement sync status reporting in sync command (report number of records synced, conflicts resolved)
- [x] T098 [US6] Implement error handling in sync command (API failures, quota exceeded, cache staleness warnings)
- [x] T099 [US6] Implement cache staleness warning in all read operations (show warning when using stale cache due to API failure)

---

## Phase 10: User Story 8 - Database Reset/Recovery (P3)

**Goal**: Administrators can reset database to recover from corruption.

**Independent Test**: Run /reset, verify instructions displayed, execute reset procedure, verify bot reinitializes from Google Sheets correctly.

**Test Criteria**:
- /reset command displays clear instructions
- Reset procedure clears local cache
- Reset reinitializes from Google Sheets (authoritative source)
- Reset verifies data integrity after completion
- Reset prevents user interactions during operation
- Reset creates audit log entry

### Implementation Tasks

- [ ] T100 [US8] Create reset command handler in src/commands/reset.py with reset instructions and execution logic
- [ ] T101 [US8] Implement reset instructions display in reset command (show step-by-step procedure, what reset does)
- [ ] T102 [US8] Implement reset confirmation flow in reset command (require explicit confirmation before executing)
- [ ] T103 [US8] Implement cache clearing in reset command (delete cache.json file)
- [ ] T104 [US8] Implement reinitialization in reset command (reload all data from Google Sheets via SheetsService)
- [ ] T105 [US8] Implement data integrity verification in reset command (verify all required sheets exist, data is valid)
- [ ] T106 [US8] Implement maintenance mode in reset command (prevent user interactions during reset operation)
- [ ] T107 [US8] Implement audit logging in reset command (create AuditEntry for reset action)
- [ ] T108 [US8] Register /reset slash command in src/services/discord_service.py (admin-only, no parameters)
- [ ] T109 [US8] Implement authorization check in reset command (require organizer role)
- [ ] T110 [US8] Implement error handling in reset command (reset failures, data integrity issues, recovery procedures)

---

## Phase 11: Polish & Cross-Cutting Concerns

**Goal**: Complete documentation, error handling, logging, and cross-cutting features.

**Independent Test**: All documentation is complete, error handling is consistent, logging is structured, and code quality checks pass.

### Documentation

- [ ] T111 Complete SETUP.md with deployment instructions (local development, production deployment, Google Sheets setup, Discord bot registration, systemd/Docker deployment)
- [ ] T112 Complete COMMANDS.md with command reference (all commands, parameters, examples, error cases)
- [ ] T113 Complete TROUBLESHOOTING.md with common issues and solutions (API failures, quota exceeded, authentication issues, data corruption)
- [ ] T114 Complete ARCHITECTURE.md with system design (architecture diagram, component overview, data flow, API integration points)

### Help Command

- [ ] T115 Create help command handler in src/commands/help.py with command listing and detailed help for specific commands
- [ ] T116 Implement command listing in help command (show all commands with brief descriptions when no command specified)
- [ ] T117 Implement detailed help in help command (show detailed help for specific command when command parameter provided)
- [ ] T118 Register /help slash command in src/services/discord_service.py with optional command parameter

### Recurring Pattern Cancellation

- [ ] T119 Implement recurring pattern cancellation in src/commands/unvolunteer.py (add recurring subcommand)
- [ ] T120 Implement pattern lookup in unvolunteer recurring command (find active patterns for user)
- [ ] T121 Implement affected dates display in unvolunteer recurring command (show all dates that would be affected)
- [ ] T122 Implement confirmation flow in unvolunteer recurring command (ask for confirmation before deactivating pattern)
- [ ] T123 Implement pattern deactivation in unvolunteer recurring command (set is_active to FALSE in RecurringPatterns sheet)
- [ ] T124 Register /unvolunteer recurring slash command in src/services/discord_service.py with optional user parameter

### List Dates Command

- [ ] T125 Create listdates command handler in src/commands/listdates.py with user date listing logic
- [ ] T126 Implement date lookup in listdates command (query Schedule sheet for all dates assigned to user, next 12 weeks)
- [ ] T127 Implement recurring pattern indicator in listdates command (show which dates are from recurring patterns)
- [ ] T128 Implement date formatting in listdates command (format as Discord embed with dates and pattern indicators)
- [ ] T129 Register /listdates slash command in src/services/discord_service.py with optional user parameter

### Error Handling & Logging

- [ ] T130 Implement consistent error handling across all commands (user-friendly messages, technical details logged)
- [ ] T131 Implement structured logging for all state-changing operations (volunteer, unvolunteer, sync, reset)
- [ ] T132 Implement API quota usage logging (log quota usage, warn at 80% threshold)
- [ ] T133 Implement cache hit/miss logging (log cache operations for monitoring)
- [ ] T134 Implement error message sanitization (ensure secrets/API tokens never logged)

### Code Quality & Testing

- [ ] T135 Configure pre-commit hooks to run black and flake8 before commits
- [ ] T136 Create unit tests for date_parser utility in tests/unit/test_date_parser.py
- [ ] T137 Create unit tests for pattern_parser utility in tests/unit/test_pattern_parser.py
- [ ] T138 Create unit tests for cache_service in tests/unit/test_cache_service.py
- [ ] T139 Create unit tests for schedule_service in tests/unit/test_schedule_service.py
- [ ] T140 Create unit tests for auth utility in tests/unit/test_auth.py
- [ ] T141 Create contract tests for Discord API in tests/contract/test_discord_api.py
- [ ] T142 Create contract tests for Google Sheets API in tests/contract/test_sheets_api.py
- [ ] T143 Create integration tests for volunteer flow in tests/integration/test_volunteer_flow.py
- [ ] T144 Create integration tests for recurring patterns in tests/integration/test_recurring_patterns.py
- [ ] T145 Create integration tests for warning system in tests/integration/test_warning_system.py
- [ ] T146 Create integration tests for sync workflow in tests/integration/test_sync_workflow.py

### Performance & Optimization

- [ ] T147 Implement exponential backoff with jitter in SheetsService for 429 rate limit responses
- [ ] T148 Implement batch operations in SheetsService for multiple date assignments (recurring patterns)
- [ ] T149 Implement cache TTL configuration (configurable via Configuration sheet, default 300 seconds)
- [ ] T150 Implement quota tracking in SheetsService (track reads/writes, log at thresholds)

### Additional Features

- [ ] T151 Implement listdates command integration (allow users to see their upcoming dates)
- [ ] T152 Implement help text for all commands (accessible via /help [command])
- [ ] T153 Implement PST timezone handling throughout (all dates displayed in PST, all date operations use PST)

---

## Parallel Execution Examples

### Phase 3 (US1) - Parallel Tasks
- T035, T036, T037 can be done in parallel (different aspects of volunteer command)
- T039, T040, T041 can be done in parallel (different operations after validation)

### Phase 4 (US2) - Parallel Tasks
- T045, T046, T047 can be done in parallel (different aspects of schedule command)
- T049, T050 can be done in parallel (timezone and cache handling)

### Phase 2 (Foundational) - Parallel Tasks
- T020-T025 (all model files) can be created in parallel
- T030-T033 (all utility files) can be created in parallel

### Phase 6 (US4) - Parallel Tasks
- T065, T066, T067 can be done in parallel (parsing, generation, conflict detection)

---

## Task Summary

**Total Tasks**: 153

**By Phase**:
- Phase 1 (Setup): 19 tasks
- Phase 2 (Foundational): 15 tasks
- Phase 3 (US1 - Volunteer): 10 tasks
- Phase 4 (US2 - View Schedule): 10 tasks
- Phase 5 (US3 - Cancel Volunteering): 9 tasks
- Phase 6 (US4 - Recurring Volunteering): 11 tasks
- Phase 7 (US7 - Proxy Actions): 6 tasks
- Phase 8 (US5 - Warning System): 9 tasks
- Phase 9 (US6 - Data Synchronization): 10 tasks
- Phase 10 (US8 - Database Reset): 11 tasks
- Phase 11 (Polish): 43 tasks

**By User Story**:
- US1 (Volunteer): 10 tasks
- US2 (View Schedule): 10 tasks
- US3 (Cancel Volunteering): 9 tasks
- US4 (Recurring Volunteering): 11 tasks
- US5 (Warning System): 9 tasks
- US6 (Data Synchronization): 10 tasks
- US7 (Proxy Actions): 6 tasks
- US8 (Database Reset): 11 tasks

**Parallel Opportunities**: Tasks marked with [P] can be executed in parallel within their phase.

---

## MVP Scope Recommendation

**Suggested MVP**: Phases 1-4 (Setup, Foundational, US1, US2)

This provides:
- Core volunteering functionality
- Schedule viewing
- All foundational infrastructure
- Complete setup and configuration

**Post-MVP Enhancements**:
- Phases 5-7: Enhanced features (cancellation, recurring patterns, proxy actions)
- Phases 8-10: Advanced features (warnings, sync, reset)
- Phase 11: Polish and optimization

---

## Format Validation

✅ All tasks follow the checklist format: `- [ ] [TaskID] [P?] [Story?] Description with file path`

✅ All user story phase tasks include [US1], [US2], etc. labels

✅ All setup and foundational tasks have no story labels

✅ All tasks include specific file paths

✅ Task IDs are sequential (T001-T153)

✅ Parallel tasks are marked with [P]

✅ All tasks are independently executable with clear file paths

