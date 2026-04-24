# Implementation Plan: Discord Host Scheduler Bot

**Branch**: `001-discord-host-scheduler` | **Date**: 2025-11-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-discord-host-scheduler/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

A Discord bot that manages host volunteering for recurring meetups through a Google Sheets backend, with automated reminders and warnings. The bot enables hosts to volunteer for specific dates or set up recurring patterns, view schedules, and receive automated warnings about unassigned dates. Technical approach: Python 3.11+ with discord.py for Discord integration, gspread for Google Sheets API, JSON file-based caching for resilience, and pytest for testing. All data is stored in Google Sheets as the authoritative source with local caching for offline resilience.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: 
- discord.py>=2.3.0 (Discord API integration with slash commands)
- gspread>=5.12.0 (Google Sheets API client)
- google-auth>=2.23.0 (Service account authentication)
- python-dateutil>=2.8.0 (Recurring pattern date calculations)

**Storage**: 
- Google Sheets (authoritative source): Schedule, RecurringPatterns, AuditLog, Configuration sheets
- Local JSON cache file (resilience): `cache.json` for offline operation and API quota management

**Testing**: pytest>=7.4.0 with pytest-asyncio>=0.21.0 and pytest-mock>=3.12.0 for async Discord bot testing and API mocking

**Target Platform**: Linux server (production), macOS/Linux (development). Bot runs as a long-lived process with systemd or Docker deployment options.

**Project Type**: Single project (Discord bot application)

**Constraints**:
- Google Sheets API quota limits (per user per 100 seconds, per project per day) - must implement batching and caching
- All dates interpreted and displayed in `America/Los_Angeles` via zoneinfo (handles DST automatically)
- Date selection via Discord slash command autocomplete only; no free-form date parsing
- First-wins concurrent booking conflict resolution, guaranteed only under single-instance deployment (see "Single-instance deployment constraint" below)
- Fail-fast behavior when API rate limits exceeded

### Single-instance deployment constraint

The bot is designed to run as a single process. The first-wins conflict guarantee in FR-004 depends on this assumption and is enforced at two layers:

1. **In-process serialization**: A module-level `asyncio.Lock` wraps every write path (`/volunteer`, `/unvolunteer`, recurring cascade, sync, reset). Only one write can be in flight within a process at a time.
2. **Sheets heartbeat lock**: A dedicated `BotInstance` row in the Configuration sheet stores `instance_id`, `started_at`, and `heartbeat_at`. On startup the bot reads this row; if `heartbeat_at` is within the last 60 seconds, the bot fatal-exits. Otherwise it writes its own `instance_id` plus fresh timestamps, sleeps 2 seconds, and re-reads the row to confirm no other instance raced it. A background task refreshes `heartbeat_at` every 30 seconds. Before every write operation the bot re-verifies that the stored `instance_id` still matches its own; if not, the write is refused.

Running multiple instances simultaneously is unsupported. Operators must stop the previous instance before starting a new one (or wait >60s after a crash for the heartbeat to expire).

**Scale/Scope**:
- Target: Community Discord server with ~50-200 active hosts
- Schedule: Up to 12 weeks of upcoming dates
- Commands: 8 user commands + 3 administrative commands
- Data volume: ~100-500 scheduled dates, ~10-50 recurring patterns

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Constitution Version**: 1.4.0

### Principle I: API Quota Management ✅
- **Status**: COMPLIANT
- **Implementation**:**
  - gspread supports batch operations for Google Sheets API calls
  - JSON file cache reduces redundant API calls with TTL-based invalidation
  - Exponential backoff with jitter will be implemented for rate limit errors (429 responses)
  - Cache TTL: 300 seconds (5 minutes) default, configurable
  - API quota usage tracking in cache metadata
  - All quality enforcement (linting, formatting) runs locally (pre-commit hooks)

### Principle II: Resilience & Fallback Strategy ✅
- **Status**: COMPLIANT
  - Google Sheets is authoritative data source; bot caches last known state
  - When Google Sheets API unavailable, bot serves from cache with staleness warning
  - Clear error messages direct users to manual Google Sheets editing
  - Automatic recovery and sync when API becomes available
  - Write operations will be idempotent to support safe retries
  - All failures logged with actionable context

### Principle III: Test Coverage for External Dependencies ✅
- **Status**: COMPLIANT
  - Contract tests will verify Discord API request/response formats
  - Contract tests will verify Google Sheets API request/response formats
  - Tests will cover rate limiting scenarios (429 responses, quota exhaustion)
  - Tests will cover cache behavior (hits, misses, staleness, invalidation)
  - Tests will cover manual sheet edit synchronization scenarios
  - Mock external APIs in unit tests; use real APIs in contract/integration tests

### Principle IV: Observability & Audit Trail ✅
- **Status**: COMPLIANT
  - AuditEntry entity defined in data-model.md for all state-changing operations
  - AuditLog sheet in Google Sheets stores all audit entries
  - Structured JSON logging for automated parsing
  - API quota usage logged per operation type
  - Cache hits/misses and staleness events will be logged
  - Error logs include request context (command, user, parameters)

### Principle V: Simplicity & Minimal Dependencies ✅
- **Status**: COMPLIANT
  - Minimal dependencies: discord.py, gspread, google-auth, python-dateutil (4 core)
  - Standard library used for: JSON caching, logging, datetime, asyncio
  - No repository pattern or complex abstractions
  - Direct API clients (discord.py, gspread) without wrapper frameworks
  - Configuration via environment variables and Google Sheets

### Principle VI: Code Documentation & Maintainability ✅
- **Status**: COMPLIANT
  - Architecture diagram will be created (text-based: Mermaid/PlantUML/ASCII)
  - Function docstrings required for all functions/methods
  - Inline comments for complex algorithms and non-obvious logic
  - Public APIs (commands) documented in quickstart.md and contracts/
  - Cross-references between documentation files

### Principle VII: Incremental Development & Version Control ✅
- **Status**: COMPLIANT
  - Feature branch: `001-discord-host-scheduler` (follows SpecKit naming)
  - Work will progress through small, focused PRs
  - Conventional commit format: `type(scope): description`
  - Each PR will include tests, documentation updates, constitution compliance check

### Principle VIII: Code Quality Enforcement ✅
- **Status**: COMPLIANT
  - Python linter: flake8 or pylint (language-standard)
  - Python formatter: black (language-standard)
  - Pre-commit hooks configured to run linters and formatters automatically
  - Pre-commit hooks block commits that fail linting/formatting
  - All quality checks run locally (no CI/CD quota usage)
  - All tests must pass before continuing (NON-NEGOTIABLE)

### Principle IX: Authentication & Authorization ✅
- **Status**: COMPLIANT
  - Three-tier role-based access control via Discord roles (role IDs in Configuration sheet: `member_role_ids`, `host_role_ids`, `admin_role_ids`)
  - All command replies are ephemeral by default for every tier; `/schedule` accepts an optional `public:true` flag to opt into a channel-visible reply, and write-action commands (`/hosting` signup/cancel) post public confirmations.
  - Members: view schedule, view own dates
  - Hosts: member capabilities plus volunteer/unvolunteer self and others
  - Admins: host capabilities plus force sync, reset, diagnostic commands, direct sheet operations
  - Role membership is managed in Discord; role→tier mapping is edited directly in the Configuration sheet (no bot commands to add/remove roles)
  - Authorization failures logged with user ID, command, timestamp
  - Clear error messages for unauthorized commands

### Principle X: Secrets Management ✅
- **Status**: COMPLIANT
  - Discord bot token stored in environment variable
  - Google Sheets service account credentials stored in environment variable
  - .env.example template will be created with placeholder values
  - Secrets never committed to version control (.env gitignored)
  - Service account OAuth (not user OAuth) for unattended operation
  - Bot validates required secrets at startup and fails fast with clear errors
  - Logs sanitized to exclude secrets/API tokens

### Principle XI: Configuration Management ✅
- **Status**: COMPLIANT
  - Configuration schema defined in data-model.md (Configuration entity)
  - Configuration stored in Google Sheets Configuration sheet
  - Configuration validated at startup (required parameters, valid ranges/formats)
  - Configuration schema documented in SETUP.md (to be created)
  - Invalid configuration logged but doesn't crash bot (uses previous valid values)

### Principle XII: Deployment Standards ✅
- **Status**: COMPLIANT (to be implemented)
  - SETUP.md will include step-by-step deployment instructions
  - Documentation will cover: local development, production deployment, Google Sheets setup, Discord bot registration
  - At least two deployment methods: direct execution (systemd) and Docker
  - Each method includes: prerequisites, installation, configuration, start/stop/restart, logs, verification
  - TROUBLESHOOTING.md will document common deployment issues

### Principle XIII: User Experience Standards ✅
- **Status**: COMPLIANT
  - All commands include help text accessible via `/help [command]`
  - `/help` with no arguments lists all commands with brief descriptions
  - Command responses are clear, concise, and actionable
  - All dates and times displayed in `America/Los_Angeles` (handles DST via zoneinfo)
  - Date inputs use Discord slash command autocomplete; no free-form date parsing
  - Error messages never show stack traces (log technical details, show friendly message)
  - Long responses formatted for readability (tables, embeds, chunked)
  - Bot acknowledges long-running commands within 3 seconds

### Gate Evaluation

**Result**: ✅ **PASSED** - All 13 principles compliant. No violations identified. Ready to proceed with Phase 0 and Phase 1.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── models/
│   ├── host.py              # Host entity
│   ├── event_date.py        # EventDate entity
│   ├── recurring_pattern.py # RecurringPattern entity
│   ├── warning.py           # Warning entity
│   ├── audit_entry.py       # AuditEntry entity
│   └── configuration.py     # Configuration entity
├── services/
│   ├── discord_service.py   # Discord bot integration (commands, events)
│   ├── sheets_service.py    # Google Sheets API integration
│   ├── cache_service.py     # JSON cache management
│   ├── schedule_service.py  # Schedule business logic
│   ├── warning_service.py   # Warning generation and posting
│   └── sync_service.py      # Data synchronization logic
├── commands/
│   ├── volunteer.py         # /volunteer command handlers
│   ├── unvolunteer.py       # /unvolunteer command handlers
│   ├── schedule.py          # /schedule command handlers
│   ├── warnings.py          # /warnings command handler
│   ├── sync.py              # /sync command handler
│   ├── reset.py             # /reset command handler
│   └── help.py              # /help command handler
├── utils/
│   ├── date_parser.py       # Date parsing and validation
│   ├── pattern_parser.py    # Recurring pattern parsing
│   ├── auth.py              # Authorization and role checking
│   └── logger.py             # Structured logging setup
└── bot.py                   # Main bot entry point and initialization

tests/
├── contract/
│   ├── test_discord_api.py  # Discord API contract tests
│   └── test_sheets_api.py   # Google Sheets API contract tests
├── integration/
│   ├── test_volunteer_flow.py      # Complete volunteer workflow
│   ├── test_recurring_patterns.py  # Recurring pattern workflows
│   ├── test_warning_system.py      # Warning generation and posting
│   └── test_sync_workflow.py       # Data synchronization workflows
└── unit/
    ├── test_date_parser.py         # Date parsing unit tests
    ├── test_pattern_parser.py      # Pattern parsing unit tests
    ├── test_cache_service.py       # Cache service unit tests
    ├── test_schedule_service.py    # Schedule service unit tests
    └── test_auth.py                # Authorization unit tests

cache.json                         # Local JSON cache (gitignored)
.env.example                       # Environment variable template
requirements.txt                   # Python dependencies
pyproject.toml                     # Project configuration (optional)
.pre-commit-config.yaml           # Pre-commit hooks configuration
README.md                          # Project overview and setup
SETUP.md                           # Deployment and configuration guide
COMMANDS.md                        # Command documentation
TROUBLESHOOTING.md                 # Common issues and solutions
ARCHITECTURE.md                    # Architecture diagram and component overview
```

**Structure Decision**: Single project structure chosen. This is a Discord bot application with no frontend or mobile components. The structure separates concerns: models (data entities), services (business logic and external API integration), commands (Discord command handlers), and utils (shared utilities). Tests are organized by type (contract, integration, unit) to match Constitution Principle III requirements.

## Complexity Tracking

> **No violations identified** - All constitution principles are compliant. The implementation follows a simple, single-project structure with minimal dependencies and standard Python practices.
