# Research: Discord Host Scheduler Bot

**Date**: 2025-11-04  
**Feature**: 001-discord-host-scheduler  
**Purpose**: Resolve NEEDS CLARIFICATION items from Technical Context in plan.md

## Research Questions

This document addresses the following unknowns from Technical Context:
1. Language/Version selection (Python vs Node.js/TypeScript)
2. Discord API library choice
3. Google Sheets API client choice
4. Date parsing approach
5. Testing framework selection

---

## 1. Language Selection: Python vs Node.js/TypeScript

### Decision: **Python 3.11+**

### Rationale

**Python Advantages**:
- **Mature Discord ecosystem**: `discord.py` is the most popular and well-maintained Discord library with excellent documentation
- **Google Sheets API**: `google-api-python-client` and `gspread` provide robust, well-documented options
- **Simplicity**: Python aligns with Constitution Principle V (Simplicity & Minimal Dependencies)
- **Standard library**: Python's `datetime` module handles date parsing well for most recurring pattern needs
- **Community support**: Large community for Discord bots in Python
- **Development speed**: Faster iteration for bot development
- **Dependency management**: `requirements.txt` or `pyproject.toml` are straightforward

**Node.js/TypeScript Considerations**:
- `discord.js` is equally mature and popular
- TypeScript adds type safety but increases complexity
- `npm` dependency management can be heavier than Python
- More verbose setup for simple bot use cases

**Why Python Chosen**: 
- Better alignment with Constitution Principle V (minimal dependencies)
- Standard library `datetime` sufficient for date parsing needs
- Simpler deployment and maintenance for community volunteers
- `discord.py` has excellent async support matching our async/await patterns

### Alternatives Considered

- **Node.js/TypeScript**: Rejected due to increased complexity and dependency weight
- **Go**: Rejected - Discord libraries less mature, overkill for bot scope
- **Rust**: Rejected - Higher complexity, Discord ecosystem smaller

---

## 2. Discord API Library

### Decision: **discord.py (version 2.3+)**

### Rationale

**discord.py Advantages**:
- **Mature and stable**: Most popular Python Discord library (500k+ downloads/month)
- **Async/await support**: Native async support aligns with concurrent API calls
- **Slash commands**: Built-in support for Discord slash commands (required for FR-001)
- **Event-driven architecture**: Clean event handling for Discord interactions
- **Active maintenance**: Regular updates, good documentation, active community
- **Rate limiting**: Built-in rate limit handling reduces manual implementation
- **Permissions**: Built-in role checking for authorization (Principle IX)

**Key Features Needed**:
- Slash command registration and handling ✅
- User/role permission checking ✅
- Message/embed formatting ✅
- Event handling for bot lifecycle ✅

### Alternatives Considered

- **discord.py-self**: Rejected - Self-bot library, violates Discord ToS
- **discord.py-interactions**: Rejected - Redundant, discord.py has native slash commands
- **py-cord**: Rejected - Fork of discord.py with less community support

### Dependencies

```python
discord.py>=2.3.0  # Discord API integration
```

---

## 3. Google Sheets API Client

### Decision: **gspread (with google-auth)**

### Rationale

**gspread Advantages**:
- **High-level API**: Simpler than raw `google-api-python-client` for common operations
- **Batch operations**: Built-in support for batch updates (supports Principle I - API Quota Management)
- **Cell-based access**: Easy to read/write specific cells and ranges
- **Authentication**: Clean service account support (required for Principle X)
- **Error handling**: Good error handling for quota limits and API failures
- **Documentation**: Clear examples and documentation

**google-api-python-client Alternative**:
- More powerful but lower-level
- Requires more boilerplate code
- Better for advanced use cases (not needed here)

**Why gspread**:
- Reduces code complexity (Principle V)
- Built-in batch operations reduce API calls (Principle I)
- Easier for future maintainers to understand

### Dependencies

```python
gspread>=5.12.0           # Google Sheets API client
google-auth>=2.23.0       # Authentication for service accounts
```

### Service Account Setup

- Uses service account OAuth (unattended operation)
- Credentials stored in environment variable (Principle X)
- Minimal scopes: `https://www.googleapis.com/auth/spreadsheets`

---

## 4. Date Parsing Approach

### Decision: **Python standard library `datetime` + `dateutil` (minimal use)**

### Rationale

**Standard Library First**:
- Python's `datetime` + `zoneinfo` cover all date/time needs; all dates are interpreted and displayed in `America/Los_Angeles` (DST handled automatically by `zoneinfo`)
- `relativedelta` from `dateutil` for recurring patterns (e.g., "every 2nd Tuesday")
- Minimal dependency addition aligns with Principle V

**Date input**:
- The bot does NOT parse free-form date strings. Date selection is via Discord slash command autocomplete populated with open (unassigned) future dates, so there is no user-facing date-parsing surface.
- Natural-language parsing libraries are therefore not needed.

**Recurring Patterns**:
- Use `dateutil.relativedelta` for patterns like:
  - "every 2nd Tuesday" → `relativedelta(weekday=TU(2))`
  - "monthly" → `relativedelta(months=1)`
- Standard library `datetime` + `dateutil.relativedelta` sufficient

### Alternatives Considered

- **python-dateutil (full)**: Accepted for `relativedelta` only
- **parsedatetime**: Rejected - Additional dependency, dateutil covers needs
- **arrow**: Rejected - Additional dependency, standard library sufficient
- **Natural language libraries (spacy, nltk)**: Rejected - Overkill, violates Principle V

### Dependencies

```python
python-dateutil>=2.8.0    # For relativedelta (recurring patterns)
```

**Note**: Consider pure standard library implementation if recurring patterns can be parsed with simple logic. Evaluate during implementation.

---

## 5. Testing Framework

### Decision: **pytest**

### Rationale

**pytest Advantages**:
- **Standard Python testing**: Most popular Python testing framework
- **Fixtures**: Excellent fixture system for mocking Discord/Google Sheets APIs
- **Async support**: `pytest-asyncio` for testing async Discord bot code
- **Plugins**: Rich plugin ecosystem for coverage, mocking, etc.
- **Contract testing**: Easy to structure contract tests for external APIs
- **Local execution**: All tests run locally (no CI/CD quota usage - Principle VIII)

**Key Testing Libraries**:
- `pytest`: Core testing framework
- `pytest-asyncio`: Async test support
- `pytest-mock`: Mocking external APIs
- `pytest-cov`: Coverage reporting (optional, for local use)

### Alternatives Considered

- **unittest**: Rejected - Less feature-rich, pytest is Python standard
- **nose2**: Rejected - Less active, pytest preferred
- **tox**: Not needed - Simple bot doesn't require multi-version testing

### Dependencies

```python
pytest>=7.4.0            # Testing framework
pytest-asyncio>=0.21.0   # Async test support
pytest-mock>=3.12.0      # Mocking support
pytest-cov>=4.1.0        # Coverage reporting (optional)
```

---

## 6. Caching & Resilience

### Decision: **JSON file-based cache (simple, no additional dependencies)**

### Rationale

**JSON File Cache**:
- **No dependencies**: Uses Python standard library `json` module
- **Simple persistence**: File-based cache survives bot restarts
- **Easy debugging**: Human-readable cache files

**SQLite Alternative**:
- Considered but rejected - adds dependency (violates Principle V)
- Overkill for simple key-value cache needs
- JSON file sufficient for cache size (~few KB)

**Cache Structure**:
```json
{
  "last_sync": "2025-11-04T12:00:00Z",
  "events": {
    "2025-11-11": {"host": "user123", "recurring": false},
    ...
  },
  "quota_usage": {"reads": 10, "writes": 2}
}
```

### Alternatives Considered

- **SQLite**: Rejected - Additional dependency, overkill
- **Redis**: Rejected - External dependency, overkill for single-server bot
- **In-memory only**: Rejected - Doesn't survive restarts (violates resilience requirement)

---

## 7. Scheduled Tasks (Daily Warning Checks)

### Decision: **asyncio + discord.py's built-in task loop**

### Rationale

**asyncio + discord.py Tasks**:
- `discord.py` provides `discord.ext.tasks` module for scheduled tasks
- No additional dependency (uses Python standard library `asyncio`)
- Built-in rate limiting and error handling
- Clean integration with Discord bot lifecycle

**Alternatives Considered**:
- **APScheduler**: Rejected - Additional dependency, discord.py tasks sufficient
- **cron**: Rejected - External dependency, less integrated with bot lifecycle

---

## 8. Logging & Observability

### Decision: **Python standard library `logging` with JSON formatter**

### Rationale

**Standard Library Logging**:
- Python `logging` module is sufficient (no dependencies)
- JSON formatter via `python-json-logger` (minimal, well-maintained)
- Structured logging for automated parsing (Principle IV)
- Console + file output for local deployment

**Alternatives Considered**:
- **structlog**: Rejected - Additional dependency, standard library sufficient
- **loguru**: Rejected - Additional dependency, standard library sufficient

### Dependencies

```python
python-json-logger>=2.0.0  # JSON log formatting (optional, can use standard library with custom formatter)
```

**Note**: Consider pure standard library JSON formatter to avoid dependency.

---

## Summary of Technology Choices

### Selected Stack

- **Language**: Python 3.11+
- **Discord Library**: discord.py 2.3+
- **Google Sheets**: gspread 5.12+ (with google-auth)
- **Date Parsing**: datetime + python-dateutil (minimal)
- **Testing**: pytest + pytest-asyncio + pytest-mock
- **Cache**: JSON file (standard library)
- **Scheduling**: discord.py tasks (asyncio)
- **Logging**: logging (standard library) + optional JSON formatter

### Dependency Count

**Core Dependencies** (required):
- discord.py
- gspread
- google-auth
- python-dateutil (or evaluate if standard library sufficient)

**Development Dependencies** (testing):
- pytest
- pytest-asyncio
- pytest-mock

**Total**: ~6-7 dependencies (minimal, aligns with Principle V)

### Constitution Compliance

✅ **Principle I (API Quota)**: gspread supports batching; will implement exponential backoff  
✅ **Principle V (Simplicity)**: Minimal dependencies chosen; standard library where possible  
✅ **Principle VIII (Code Quality)**: pytest standard for Python; pre-commit hooks with black/flake8  
✅ **Principle X (Secrets)**: Service account OAuth via google-auth; env vars for credentials  

---

## Remaining Decisions (Implementation Phase)

1. **Date parsing complexity**: Evaluate if pure standard library sufficient for recurring patterns
2. **JSON log formatter**: Implement custom JSON formatter vs `python-json-logger`
3. **Cache TTL**: Determine appropriate cache TTL for Google Sheets data
4. **Batch size**: Determine optimal batch size for Google Sheets API calls

These will be resolved during implementation with measurements and testing.

