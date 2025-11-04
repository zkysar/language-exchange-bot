<!--
Sync Impact Report - Constitution Update
=========================================
Version Change: 1.3.0 → 1.4.0
Rationale: MINOR version bump - Added TypeScript language requirement to Principle VIII

Modified Principles:
  - VIII. Code Quality Enforcement - Added requirement that all TypeScript/JavaScript code must be written in TypeScript

Modified Sections:
  - Principle VIII - Added TypeScript language requirement
  - Development Workflow > Quality Gates - Added TypeScript verification check
  - Development Workflow > Code Review Process - Added TypeScript verification item

Templates Requiring Updates:
  ✅ .specify/templates/plan-template.md - Constitution Check section compatible (no changes needed)
  ✅ .specify/templates/spec-template.md - No changes needed
  ✅ .specify/templates/tasks-template.md - No changes needed

Follow-up TODOs: None - all placeholders filled
=========================================
-->

# Discord Host Scheduler Bot Constitution

## Core Principles

### I. API Quota Management (NON-NEGOTIABLE)

All external API integrations MUST implement quota-aware request handling:

- Google Sheets API calls MUST be batched where possible to minimize request count
- System MUST implement exponential backoff with jitter for rate limit errors (429 responses)
- System MUST cache API responses with appropriate TTL to reduce redundant calls
- System MUST monitor and log API quota usage to prevent unexpected quota exhaustion
- System MUST gracefully degrade when quota limits are approached (e.g., delay
  non-critical operations)
- Daily API usage MUST be tracked and alerting configured at 80% of quota threshold
- All quality enforcement MUST run locally (pre-commit hooks, linters) with zero server
  quota usage

**Rationale**: Google Sheets API has strict quota limits (per user per 100 seconds, per
project per day). Exceeding these limits causes service disruption. Quota management is
non-negotiable for reliable bot operation in production. Local-only tooling prevents
wasting quota on CI/CD infrastructure.

### II. Resilience & Fallback Strategy

System MUST provide graceful degradation when dependencies fail:

- Google Sheets is the authoritative data source; bot MUST cache last known state
- When Google Sheets API is unavailable, bot MUST serve from cache with staleness warning
- Bot MUST provide clear error messages directing users to manual Google Sheets editing
- Bot MUST automatically recover and sync when API becomes available again
- All write operations MUST be idempotent to support safe retries
- System MUST log all failures with actionable context for troubleshooting

**Rationale**: Volunteer coordination is time-sensitive. The system must remain useful
even during partial outages. Manual Google Sheets access provides essential fallback.

### III. Test Coverage for External Dependencies

Integration points with Discord and Google Sheets MUST have contract tests:

- Contract tests MUST verify expected request/response formats for both APIs
- Tests MUST cover rate limiting scenarios (429 responses, quota exhaustion)
- Tests MUST cover cache behavior (hits, misses, staleness, invalidation)
- Tests MUST cover manual sheet edit synchronization scenarios
- Tests MUST validate error message clarity for user-facing failures
- Mock external APIs in unit tests; use real APIs in contract/integration tests

**Rationale**: External API changes can break the bot silently. Contract tests detect
API breaking changes early. Rate limit testing ensures quota management actually works.

### IV. Observability & Audit Trail

All user actions and system state changes MUST be logged for debugging and accountability:

- Every volunteer/unvolunteer action MUST create an audit entry with timestamp, user,
  date affected, and outcome
- Warning generation and posting MUST be logged with severity and target channel
- API quota usage MUST be logged per operation type (read, write, batch)
- Cache hits/misses and staleness events MUST be logged for performance analysis
- Error logs MUST include request context (command, user, parameters) for reproduction
- Logs MUST be structured (JSON) for automated parsing and alerting

**Rationale**: Distributed systems require comprehensive logging for debugging. Audit
trails provide accountability for scheduling changes. Quota logs enable proactive
capacity planning.

### V. Simplicity & Minimal Dependencies

Keep the implementation simple and maintainable:

- Minimize external dependencies to reduce maintenance burden and attack surface
- Prefer standard library solutions over third-party libraries where reasonable
- Avoid premature abstractions (e.g., repository pattern, complex event systems)
- Use direct API clients for Discord and Google Sheets without wrapper frameworks
- Configuration MUST be environment variables or Google Sheets-based (no complex
  config systems)
- Code MUST be documented inline for future maintainers unfamiliar with the project

**Rationale**: This bot is intended for community use with minimal operational overhead.
Simpler code with fewer dependencies is easier to deploy, debug, and hand off.

### VI. Code Documentation & Maintainability

Code MUST be documented for future maintainers who are unfamiliar with the project:

- Every function/method MUST have a concise docstring explaining purpose, parameters,
  return values, and side effects
- Complex algorithms or non-obvious logic MUST have inline comments explaining "why",
  not "what"
- Public APIs (commands, configuration) MUST be documented in user-facing docs
  (COMMANDS.md, SETUP.md)
- Architecture MUST be documented with a text-based diagram (Mermaid, PlantUML, or ASCII)
  showing major components and data flows
- Architecture diagram MUST be version-controlled alongside code and easily updated
- Documentation MUST be concise - avoid over-documenting obvious code; focus on rationale
  and context
- Documentation MUST be easily browsable with cross-references and backlinks between
  related sections
- All documentation files MUST include navigation links to related documents (e.g.,
  SETUP.md links to COMMANDS.md, ARCHITECTURE.md, TROUBLESHOOTING.md)
- Complex features MUST include "See also" sections pointing to related documentation
- Code comments SHOULD reference relevant documentation files when explaining
  design decisions

**Rationale**: This bot may be handed off to new maintainers or community contributors.
Clear, concise documentation enables others to understand and modify the code without
original author assistance. Text-based diagrams stay in sync with code through version
control. Cross-references and backlinks make documentation navigable and reduce time
spent searching for information.

### VII. Incremental Development & Version Control

All work MUST progress through small, incremental changes:

- Pull requests MUST be focused on a single feature or fix (avoid mega-PRs)
- Commits MUST be atomic and self-contained (each commit should leave code in working
  state)
- Commit messages MUST follow conventional commit format (type(scope): description)
- Features MUST be developed behind feature flags or as disabled-by-default when
  appropriate
- Branches MUST follow naming convention: `NNN-feature-name` per SpecKit workflow
- Each PR MUST include tests, documentation updates, and constitution compliance check
- Large features MUST be broken into multiple PRs delivering incremental value

**Rationale**: Small, focused changes are easier to review, test, and rollback. GitHub
history becomes a useful debugging and learning tool. Incremental delivery reduces risk
and provides faster feedback cycles.

### VIII. Code Quality Enforcement (NON-NEGOTIABLE)

Code quality standards MUST be enforced locally with zero server quota usage:

- Project MUST use language-standard linters (e.g., pylint/flake8 for Python,
  ESLint for TypeScript)
- Project MUST use language-standard formatters (e.g., black/autopep8 for Python,
  Prettier for TypeScript)
- All TypeScript/JavaScript code MUST be written in TypeScript (no plain JavaScript
  files allowed)
- TypeScript configuration MUST enforce strict type checking
- Pre-commit hooks MUST be configured to run linters and formatters automatically
- Pre-commit hooks MUST block commits that fail linting or formatting checks
- Pre-commit configuration MUST be committed to repository (e.g., `.pre-commit-config.yaml`)
- Linting rules MUST follow language community best practices (avoid custom style
  preferences)
- All quality checks MUST run locally on developer machines (no CI/CD quota usage)
- README MUST include setup instructions for installing pre-commit hooks
- All tests MUST pass before continuing to the next task or feature (NON-NEGOTIABLE)
- Developers MUST NOT proceed with new implementation if existing tests are failing
- Test failures MUST be fixed immediately or the failing change MUST be reverted
- Test-Driven Development (TDD) is NOT required - tests can be written before or after
  implementation based on developer preference
- However, once tests exist, they MUST pass before any continuation

**Rationale**: Consistent code style improves readability and reduces cognitive load for
maintainers. Automated enforcement prevents style debates and catches common bugs early.
TypeScript provides static type checking that catches errors at compile time, improving
code quality and maintainability. Local-only execution preserves API quotas for production
use. Pre-commit hooks catch issues before they enter version control. Requiring test passage
ensures code quality and prevents regressions, while allowing flexibility in when tests are
written.

### IX. Authentication & Authorization (NON-NEGOTIABLE)

All bot commands MUST implement proper authentication and authorization controls:

- Bot MUST verify Discord user identity for all commands that modify state
- Role-based access control MUST be implemented for administrative operations:
  - Standard users: Can volunteer/unvolunteer for themselves, view schedules
  - Host-privileged users: Can volunteer/unvolunteer on behalf of any user
  - Admin users: Can modify configuration, force sync, access diagnostic commands
- Bot MUST reject unauthorized commands with clear error messages explaining required
  permissions
- Admin-only commands (e.g., /sync, /warnings, configuration changes) MUST be restricted
  to users with designated admin role(s)
- Role requirements MUST be configurable via Google Sheets or environment variables
- Default configuration MUST be secure (minimal permissions, admin commands disabled for
  non-admins)
- Authorization failures MUST be logged with user ID, command attempted, and timestamp

**Rationale**: Volunteer scheduling requires trust and accountability. Without proper
authorization, malicious users could disrupt schedules or impersonate others. Role-based
controls enable delegation (hosts helping hosts) while protecting critical operations.
Logging authorization failures enables security auditing and incident response.

### X. Secrets Management (NON-NEGOTIABLE)

API credentials and sensitive configuration MUST be handled securely:

- API keys, tokens, and credentials MUST be stored in environment variables, never
  hard-coded
- Environment variable names MUST be documented in SETUP.md with example values
- Secrets MUST NEVER be committed to version control (.env files MUST be gitignored)
- Repository MUST include .env.example template with placeholder values showing
  required format
- Bot MUST validate presence of required secrets at startup and fail fast with clear
  error messages
- Google Sheets API credentials MUST use service account OAuth (not user OAuth) for
  unattended operation
- Discord bot token MUST have minimal required scopes (no administrator permission)
- Secrets rotation procedures MUST be documented in SETUP.md (how to update without
  downtime)
- Logs MUST NOT contain secrets or API tokens (sanitize before logging)

**Rationale**: Leaked credentials enable unauthorized access to Discord bot control and
Google Sheets data. Environment variables provide standard secure storage across
deployment environments. Service accounts enable bot operation without user login.
Minimal scopes limit blast radius of token compromise. Documentation ensures operators
can rotate credentials safely during security incidents.

### XI. Configuration Management

All configuration options MUST be documented and validated:

- Configuration schema MUST be documented in SETUP.md with:
  - Parameter name (environment variable or Google Sheets cell reference)
  - Type (string, integer, boolean, date format, etc.)
  - Required vs. optional
  - Default value (if optional)
  - Valid range or allowed values
  - Example value
  - Impact of changing (e.g., "affects warning timing", "requires bot restart")
- Bot MUST validate all configuration at startup:
  - Required parameters present
  - Values within valid range/format
  - Dependencies satisfied (e.g., if feature X enabled, parameter Y required)
- Validation failures MUST fail fast with clear error messages citing specific parameter
  and expected format
- Configuration changes requiring bot restart MUST be clearly marked in documentation
- Google Sheets-based configuration MUST have header rows documenting each column's
  purpose
- Invalid configuration in Google Sheets MUST be logged but MUST NOT crash the bot
  (use previous valid values)

**Rationale**: Undocumented configuration leads to operational errors and frustrating
debugging. Startup validation catches errors before production use. Clear error messages
enable operators to fix configuration quickly. Graceful handling of invalid Sheets data
prevents manual editing mistakes from causing outages.

### XII. Deployment Standards

Deployment procedures MUST be fully documented for operational success:

- SETUP.md MUST include step-by-step deployment instructions for:
  - Local development setup (dependencies, environment, running locally)
  - Production deployment (recommended hosting options with specific instructions)
  - Google Sheets setup (template creation, sharing, service account access)
  - Discord bot registration (token creation, permissions, server integration)
- Deployment documentation MUST cover at least two deployment methods:
  - Simple: Direct execution (python/node script, systemd service)
  - Containerized: Docker/Docker Compose with example configurations
- Each deployment method MUST include:
  - Prerequisites (runtime version, system packages)
  - Installation steps
  - Configuration file locations
  - How to start/stop/restart the bot
  - How to view logs
  - How to verify bot is running correctly
- Common deployment issues MUST be documented in TROUBLESHOOTING.md
- Upgrade procedures MUST be documented (how to update to new version without data loss)

**Rationale**: Community volunteers deploying the bot need clear, complete instructions.
Multiple deployment options accommodate different skill levels and infrastructure
preferences. Troubleshooting documentation reduces support burden. Documented upgrade
paths enable safe updates as the bot evolves.

### XIII. User Experience Standards

Bot commands MUST be intuitive and user-friendly:

- All commands MUST include help text accessible via /help [command]
- /help with no arguments MUST list all available commands with brief descriptions
- Command responses MUST be clear, concise, and actionable:
  - Success: Confirm action taken and show relevant state
  - Errors: Explain what went wrong and how to fix it
  - Warnings: Clearly distinguish from errors (different formatting/emoji)
- All dates and times MUST be displayed in Pacific Standard Time (PST/PDT)
- Date inputs MUST accept multiple formats: YYYY-MM-DD, MM/DD/YYYY, natural language
  ("next Tuesday", "Dec 25")
- Date outputs MUST use consistent format: "Day, Month DD, YYYY" (e.g., "Tuesday,
  December 25, 2024")
- Error messages MUST NEVER show stack traces to end users (log technical details,
  show friendly message)
- Long responses (e.g., schedule listings) MUST be formatted for readability (tables,
  embeds, or chunked)
- Bot MUST acknowledge long-running commands within 3 seconds (e.g., "Processing...")
  even if full response takes longer

**Rationale**: Discord communities have varying technical expertise. Clear help text
enables self-service. Consistent timezone handling prevents scheduling confusion across
distributed communities. Multiple date formats reduce friction. User-friendly error
messages reduce support burden and improve adoption. Fast acknowledgment prevents users
from thinking commands failed.

## Performance & Reliability Standards

### Response Time Targets

- Discord command responses MUST acknowledge within 3 seconds (even if processing
  continues async)
- Google Sheets updates MUST complete within 5 seconds for 95% of operations
- Schedule queries MUST return within 3 seconds for up to 12 weeks of data
- Cache lookups MUST complete in under 100ms

### Uptime & Data Integrity

- System MUST maintain 99% uptime over 30-day periods (excluding planned maintenance)
- Zero data loss during bot restarts or temporary outages (cache must be persisted)
- All Google Sheets write operations MUST be verified with read-after-write checks
- Bot MUST gracefully handle Discord disconnections and reconnect automatically

### Error Budget

- Google Sheets API failures at 80%+ quota usage are expected; MUST handle gracefully
- Up to 5% of operations may experience temporary failures due to rate limiting
- All user-facing errors MUST provide actionable guidance (never show stack traces)

## Development Workflow

### Quality Gates

Before merging any feature:

1. **Constitution Compliance Check**:
   - Verify API quota management is implemented (batching, caching, rate limit handling)
   - Verify fallback behavior when Google Sheets API is unavailable
   - Verify contract tests exist for Discord and Google Sheets integrations
   - Verify audit logging for all state-changing operations
   - Verify no unnecessary dependencies were added
   - Verify inline documentation exists for functions and complex logic
   - Verify architecture diagram updated if component structure changed
   - Verify pre-commit hooks configured and passing
   - Verify code follows linting and formatting standards
   - Verify all TypeScript/JavaScript code is written in TypeScript with strict type checking
   - Verify all tests pass (no failing tests allowed before proceeding)
   - Verify documentation has proper cross-references and backlinks
   - Verify authentication/authorization implemented for commands (Principle IX)
   - Verify no secrets committed; .env.example updated if new secrets added (Principle X)
   - Verify configuration schema documented and validated at startup (Principle XI)
   - Verify deployment documentation updated if deployment process changed (Principle XII)
   - Verify command help text exists and dates use PST timezone (Principle XIII)

2. **Testing Requirements**:
   - Contract tests MUST pass for all external API interactions
   - Integration tests MUST cover complete user journeys (volunteer → sheet update →
     confirmation)
   - Rate limit scenarios MUST be tested (mock 429 responses, verify backoff behavior)
   - Cache invalidation and synchronization MUST be tested
   - Authorization controls MUST be tested (verify admin-only commands reject
     non-admins)
   - All tests MUST run locally (no CI/CD quota usage)
   - All tests MUST pass before continuing to next task (NON-NEGOTIABLE)
   - Test-Driven Development (TDD) is NOT mandatory - tests may be written before
     or after implementation
   - Failing tests MUST be fixed or reverted immediately; no work proceeds with
     failing tests

3. **Documentation Requirements**:
   - All public commands MUST be documented in COMMANDS.md with examples
   - Setup instructions MUST be updated if new environment variables or dependencies added
   - Troubleshooting guide MUST include new error scenarios with solutions
   - Configuration schema MUST be updated in SETUP.md if new config options added
   - Architecture diagram (docs/ARCHITECTURE.md or ARCHITECTURE.md) MUST be updated if:
     - New components added (e.g., cache layer, scheduler)
     - Data flow changes (e.g., new API integration)
     - System boundaries change (e.g., new external dependency)
   - Architecture diagram MUST be text-based (Mermaid, PlantUML, or ASCII art) for easy
     version control
   - Inline code documentation MUST explain "why" for non-obvious logic
   - All documentation files MUST include cross-references to related documents
   - Documentation MUST have clear navigation structure (table of contents, backlinks)

### Code Review Process

All pull requests MUST:

- Be small and focused (single feature/fix - split large changes into multiple PRs)
- Include rationale for any new dependencies (justify against Principle V)
- Demonstrate quota usage impact for any new Google Sheets API calls
- Show test coverage for contract tests and integration tests
- Include inline documentation for non-obvious logic
- Pass linting and formatting checks (enforced by pre-commit hooks)
- Use TypeScript for all TypeScript/JavaScript code (no plain JavaScript files)
- Update architecture diagram if component structure changed
- Follow conventional commit message format
- Have all tests passing (no exceptions)
- Include documentation cross-references where appropriate
- Document new configuration options in SETUP.md schema
- Update .env.example if new secrets added
- Include authorization checks for new commands
- Include help text for new commands with PST timezone handling

Reviewers MUST verify:

- Constitution compliance (all 13 principles addressed)
- No security vulnerabilities (credential leaks, command injection, XSS in embeds,
  authorization bypasses)
- Error messages are user-friendly and actionable
- Logging includes sufficient context for debugging
- Documentation is concise and sufficient for future maintainers
- Changes are appropriately sized (reject mega-PRs, suggest splitting)
- Code style follows language best practices
- TypeScript used for all TypeScript/JavaScript code with strict type checking
- All tests pass before approval
- Documentation has proper navigation and cross-references
- Secrets properly managed (environment variables, not hard-coded)
- Configuration validated at startup
- Command help text exists and dates displayed in PST

## Governance

### Amendment Procedure

This constitution MUST be amended when:

- New external dependencies are added (update Principle V justification)
- New API integrations are introduced (update Principles I and III)
- Quality gates need adjustment based on operational experience
- Principles conflict with practical implementation needs
- Security requirements change (e.g., new authentication methods needed)

To amend:

1. Propose change with rationale in pull request
2. Document impact on existing features and tests
3. Update all affected templates (plan, spec, tasks)
4. Increment version using semantic versioning:
   - MAJOR: Remove/redefine principles (breaking governance change)
   - MINOR: Add principles or materially expand guidance
   - PATCH: Clarify wording, fix typos, non-semantic refinements
5. Update LAST_AMENDED_DATE to current date

### Compliance Review

Project maintainers MUST review constitution compliance:

- Before accepting any pull request (via quality gates above)
- Quarterly to assess if principles remain appropriate as project evolves
- After any production incident to determine if constitution changes needed

Non-compliance without justification is grounds for rejecting pull requests.

### Versioning Policy

All features MUST reference the constitution version they comply with in their plan.md
"Constitution Check" section. This enables tracking which features need review when
constitution is amended with breaking changes.

**Version**: 1.4.0 | **Ratified**: 2025-11-04 | **Last Amended**: 2025-11-04
