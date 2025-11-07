# Testing Guide: Discord Host Scheduler Bot

This guide explains how to test the current implementation.

## Phase 1 & 2 Status

✅ **Completed**: Foundational infrastructure (models, services, utilities)
⏳ **Not Yet**: Discord commands (coming in Phase 3)

## Quick Start: Run Unit Tests

### 1. Install Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Run All Unit Tests

```bash
# Run all tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_models.py -v
pytest tests/unit/test_date_parser.py -v
pytest tests/unit/test_cache_service.py -v
```

### 3. Expected Output

```
tests/unit/test_models.py::TestHostModel::test_create_host_valid PASSED
tests/unit/test_models.py::TestHostModel::test_host_invalid_discord_id_short PASSED
tests/unit/test_date_parser.py::TestParseDateValidFormat::test_parse_valid_date PASSED
tests/unit/test_cache_service.py::TestCacheService::test_set_and_get_value PASSED
...
```

## Manual Testing Components

### Test 1: Model Validation

Test that models properly validate input:

```python
from src.models import Host, EventDate
from datetime import date

# Valid host
host = Host(discord_id="123456789012345678", discord_username="testuser#1234")
print(f"Created host: {host}")

# Invalid host (should raise ValueError)
try:
    invalid_host = Host(discord_id="123")  # Too short
except ValueError as e:
    print(f"Caught expected error: {e}")

# Event date
event = EventDate(date=date(2025, 11, 11))
print(f"Event assigned: {event.is_assigned()}")  # False
```

### Test 2: Date Parser Utility

Test date parsing and PST timezone handling:

```python
from src.utils.date_parser import (
    parse_date,
    validate_date_format_and_future,
    format_date_pst,
    get_current_date_pst
)
from datetime import date, timedelta

# Parse date
parsed = parse_date("2025-11-11")
print(f"Parsed date: {parsed}")

# Format date in PST
formatted = format_date_pst(date(2025, 11, 11))
print(f"Formatted: {formatted}")

# Get current date in PST
today_pst = get_current_date_pst()
print(f"Today (PST): {today_pst}")

# Validate future date
future_date = today_pst + timedelta(days=7)
try:
    validate_date_format_and_future(future_date.isoformat())
    print("Future date validated successfully")
except ValueError as e:
    print(f"Validation failed: {e}")
```

### Test 3: Pattern Parser

Test recurring pattern parsing:

```python
from src.utils.pattern_parser import (
    parse_pattern_description,
    generate_dates_from_pattern
)
from datetime import date

# Parse pattern description
pattern = parse_pattern_description("every 2nd Tuesday")
print(f"Pattern: {pattern}")

# Generate dates
dates = generate_dates_from_pattern(
    pattern,
    start_date=date(2025, 11, 1),
    end_date=None,
    months=3
)
print(f"Generated {len(dates)} dates:")
for d in dates:
    print(f"  - {d.strftime('%A, %B %d, %Y')}")
```

### Test 4: Cache Service

Test cache operations:

```python
from src.services.cache_service import CacheService
import os

# Create cache
cache = CacheService(cache_file="test_cache.json", ttl_seconds=300)

# Store event
cache.set("events", "2025-11-11", {
    "host_discord_id": "123456789012345678",
    "host_username": "testuser#1234"
})

# Retrieve event
event = cache.get("events", "2025-11-11")
print(f"Cached event: {event}")

# Check if stale
print(f"Cache is stale: {cache.is_stale()}")

# Update timestamp
cache.update_sync_timestamp()
print(f"After update, cache is stale: {cache.is_stale()}")

# Cleanup
cache.clear()
```

### Test 5: Configuration Model

Test configuration with different types:

```python
from src.models import Configuration, SettingType, get_default_configurations

# Get default configurations
defaults = get_default_configurations()
print(f"Default configurations: {len(defaults)} entries")

for config in defaults[:3]:
    print(f"  {config.setting_key}: {config.setting_value} ({config.setting_type.value})")

# Create and parse typed config
config = Configuration(
    setting_key="warning_passive_days",
    setting_value="7",
    setting_type=SettingType.INTEGER
)
print(f"Typed value: {config.get_typed_value()} (type: {type(config.get_typed_value()).__name__})")
```

## Integration Testing (Requires Setup)

### Setup Google Sheets

To test Google Sheets integration, you need:

1. **Create a Google Sheets document** with these sheets:
   - Schedule
   - RecurringPatterns
   - AuditLog
   - Configuration

2. **Add headers** to each sheet (see `specs/001-discord-host-scheduler/data-model.md`)

3. **Create service account**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create project
   - Enable Google Sheets API
   - Create service account
   - Download JSON key file
   - Share your spreadsheet with service account email

4. **Set up .env file**:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

5. **Test SheetsService**:
   ```python
   from src.services.sheets_service import SheetsService
   import os
   from dotenv import load_dotenv

   load_dotenv()

   sheets = SheetsService(
       spreadsheet_id=os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID"),
       credentials_file=os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE")
   )

   # Test reading configuration
   config = sheets.read_all_records(sheets.SHEET_CONFIGURATION)
   print(f"Configuration entries: {len(config)}")
   ```

## What's Not Yet Testable

The following components require Phase 3+ implementation:

- ❌ Discord slash commands (`/volunteer`, `/schedule`, etc.)
- ❌ Discord bot running and responding to commands
- ❌ End-to-end user flows
- ❌ Warning system
- ❌ Recurring pattern assignment

These will be testable after Phase 3 (User Story 1) is complete.

## Test Coverage Goals

Current test coverage:
- ✅ Models: Validation, serialization/deserialization
- ✅ Date parser: Format validation, PST timezone
- ✅ Cache service: CRUD operations, TTL, quota tracking
- ⏳ Sheets service: Requires Google Sheets setup
- ⏳ Discord service: Requires Discord bot token
- ⏳ Sync service: Requires both Sheets and Cache

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError: No module named 'src'`:

```bash
# Make sure you're in the project root
cd /Users/zachkysar/projects/language-exchange-bot

# Install in development mode
pip install -e .
```

Or run tests with Python path:

```bash
PYTHONPATH=. pytest tests/unit/ -v
```

### Test Failures

If tests fail due to timezone issues:
- Ensure `pytz` is installed: `pip install pytz`
- Check your system timezone settings

## Next Steps

After validating Phase 1 & 2:
1. ✅ Run unit tests to verify models and utilities
2. ✅ Optionally set up Google Sheets for integration testing
3. ➡️ Proceed to Phase 3 to implement `/volunteer` command
4. ➡️ Test end-to-end user flows with Discord bot

## Quick Test Commands

```bash
# Run all tests with verbose output
pytest tests/unit/ -v

# Run tests with coverage report
pytest tests/unit/ --cov=src --cov-report=term-missing

# Run specific test class
pytest tests/unit/test_models.py::TestHostModel -v

# Run tests in watch mode (requires pytest-watch)
ptw tests/unit/
```
