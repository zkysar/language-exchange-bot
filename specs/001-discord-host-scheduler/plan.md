# Implementation Plan: Discord Host Scheduler Bot

**Branch**: `001-discord-host-scheduler` | **Date**: 2025-11-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-discord-host-scheduler/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

A Discord bot that manages host volunteering for recurring meetups through Google Sheets backend. The bot enables hosts to volunteer for specific dates or set up recurring patterns, view schedules, cancel commitments, and automatically warns about unassigned dates. All data is stored in Google Sheets as the authoritative source, with local caching for resilience. The system includes role-based access control, comprehensive audit logging, and graceful degradation when APIs are unavailable.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.11+  
**Primary Dependencies**: discord.py 2.3+ (Discord API), gspread 5.12+ + google-auth (Google Sheets API), python-dateutil 2.8+ (date parsing for recurring patterns)  
**Storage**: Google Sheets (authoritative) + local JSON cache file (resilience layer)  
**Testing**: pytest 7.4+ with pytest-asyncio and pytest-mock (contract tests for Discord/Google Sheets APIs)  
**Target Platform**: Linux server (deployable via Docker, systemd, or direct execution)  
**Project Type**: single (Discord bot application)
**Constraints**: Google Sheets API quota limits (per-user-per-100-seconds, per-project-per-day); Must cache to handle API failures gracefully; Must implement exponential backoff for rate limits  

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Constitution Version**: 1.3.0

### I. API Quota Management (NON-NEGOTIABLE) ✅
- **Status**: REQUIREMENT - Must implement batching, caching, exponential backoff
- **Implementation**: Google Sheets API calls will be batched; cache with TTL; exponential backoff with jitter for 429 responses; quota monitoring and logging
- **Risk**: LOW - Standard patterns available

### II. Resilience & Fallback Strategy ✅
- **Status**: REQUIREMENT - Google Sheets is authoritative; cache last known state
- **Implementation**: Local cache file; serve from cache with staleness warning when API unavailable; automatic sync recovery
- **Risk**: LOW - Design aligns with requirement

### III. Test Coverage for External Dependencies ✅
- **Status**: REQUIREMENT - Contract tests for Discord and Google Sheets APIs
- **Implementation**: Mock APIs in unit tests; contract tests verify request/response formats; rate limit scenarios tested
- **Risk**: LOW - Standard testing approach

### IV. Observability & Audit Trail ✅
- **Status**: REQUIREMENT - All actions logged with structured JSON
- **Implementation**: Audit log for volunteer/unvolunteer; warning generation logged; API quota usage logged; cache events logged
- **Risk**: LOW - Straightforward logging requirement

### V. Simplicity & Minimal Dependencies ⚠️
- **Status**: GATE - Minimize external dependencies; prefer standard library
- **Implementation**: Will evaluate Discord library choice (discord.py vs discord.js) and Google Sheets client; avoid wrapper frameworks
- **Risk**: MEDIUM - Need to research and justify dependency choices

### VI. Code Documentation & Maintainability ✅
- **Status**: REQUIREMENT - Docstrings, inline comments, architecture diagram
- **Implementation**: All functions documented; architecture diagram in text format; cross-referenced documentation
- **Risk**: LOW - Standard practice

### VII. Incremental Development & Version Control ✅
- **Status**: REQUIREMENT - Small PRs, conventional commits, feature flags
- **Implementation**: Follow SpecKit workflow; atomic commits; conventional commit format
- **Risk**: LOW - Process requirement

### VIII. Code Quality Enforcement (NON-NEGOTIABLE) ✅
- **Status**: REQUIREMENT - Pre-commit hooks, linters, formatters, all tests pass
- **Implementation**: Language-standard linters/formatters; pre-commit hooks; local-only execution
- **Risk**: LOW - Standard setup

### IX. Authentication & Authorization (NON-NEGOTIABLE) ✅
- **Status**: REQUIREMENT - Role-based access control for commands
- **Implementation**: Discord role verification; standard users vs host-privileged vs admin roles; configurable via Google Sheets/env vars
- **Risk**: LOW - Discord provides role API

### X. Secrets Management (NON-NEGOTIABLE) ✅
- **Status**: REQUIREMENT - Environment variables, .env.example, no hardcoding
- **Implementation**: All secrets in env vars; .env.example template; service account OAuth for Google Sheets; Discord token with minimal scopes
- **Risk**: LOW - Standard practice

### XI. Configuration Management ✅
- **Status**: REQUIREMENT - Schema documented, startup validation
- **Implementation**: SETUP.md with configuration schema; startup validation; Google Sheets config with headers
- **Risk**: LOW - Documentation and validation requirement

### XII. Deployment Standards ✅
- **Status**: REQUIREMENT - Deployment docs with multiple methods
- **Implementation**: SETUP.md with local dev and production deployment; Docker and direct execution options; troubleshooting guide
- **Risk**: LOW - Documentation requirement

### XIII. User Experience Standards ✅
- **Status**: REQUIREMENT - Help text, PST timezone, multiple date formats
- **Implementation**: /help command with detailed help; PST for all dates/times; multiple date input formats; friendly error messages
- **Risk**: LOW - UX requirements

### Gate Evaluation (Post-Design)

**PASS**: All principles are requirements that will be implemented. Principle V (Simplicity) research completed - minimal dependencies chosen (discord.py, gspread, python-dateutil). No violations identified.

**Post-Design Verification**:
1. ✅ Language choice (Python 3.11+) justified in research.md
2. ✅ Dependency choices (discord.py, gspread) justified in research.md
3. ✅ Date parsing approach (standard library + dateutil) justified in research.md
4. ✅ Testing framework (pytest) standard for Python
5. ✅ Cache approach (JSON file) minimal, no additional dependencies
6. ✅ Google Sheets API quota management addressed in contracts
7. ✅ Resilience patterns (cache fallback) documented in data-model.md
8. ✅ Authorization requirements documented in contracts
9. ✅ Secrets management approach documented (env vars, service account)
10. ✅ Configuration schema documented in data-model.md

**Constitution Compliance**: ✅ PASS - All principles addressed with no violations.

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
├── models/          # Entity definitions (Host, EventDate, RecurringPattern, Warning, AuditEntry, Config)
├── services/        # Business logic (VolunteerService, ScheduleService, WarningService, SyncService)
├── commands/        # Discord slash command handlers
├── api/             # External API integrations (Discord, Google Sheets)
├── cache/           # Caching layer for resilience
└── utils/           # Shared utilities (date parsing, validation, logging)

tests/
├── contract/        # Contract tests for Discord and Google Sheets APIs
├── integration/     # End-to-end integration tests
└── unit/            # Unit tests for services, models, utilities

docs/
├── ARCHITECTURE.md  # System architecture diagram and component descriptions
├── COMMANDS.md      # User-facing command documentation
├── SETUP.md         # Deployment and configuration documentation
└── TROUBLESHOOTING.md # Common issues and solutions
```

**Structure Decision**: Single project structure chosen (Discord bot application). Source code in `src/` with clear separation: models (entities), services (business logic), commands (Discord handlers), api (external integrations), cache (resilience layer), utils (shared utilities). Tests mirror source structure with contract/integration/unit separation. Documentation in `docs/` directory.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
