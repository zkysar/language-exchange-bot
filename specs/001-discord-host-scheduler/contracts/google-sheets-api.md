# Google Sheets API Contracts

**Date**: 2025-11-04  
**Feature**: 001-discord-host-scheduler  
**API Type**: Google Sheets API v4

## Overview

This document defines the Google Sheets API usage patterns for the Host Scheduler Bot. All data operations must comply with API quota limits and implement resilience patterns per Constitution Principles I and II.

---

## Authentication

**Method**: Service Account OAuth (unattended operation)

**Required Scopes**:
- `https://www.googleapis.com/auth/spreadsheets`

**Credentials Storage**:
- Service account JSON key stored in environment variable `GOOGLE_SHEETS_CREDENTIALS` (JSON string) or `GOOGLE_SHEETS_CREDENTIALS_FILE` (file path)
- Never hardcoded (Principle X)

**Contract Test Requirements**:
- Verify service account authentication
- Verify credentials loaded from environment
- Verify no credentials in code

---

## Sheet Structure

### Sheet: "Schedule"

**Range**: `Schedule!A:G` (or full sheet)

**Columns**:
- A: `date` (YYYY-MM-DD format)
- B: `host_discord_id` (Discord snowflake)
- C: `host_username` (Display name)
- D: `recurring_pattern_id` (UUID or generated ID)
- E: `assigned_at` (ISO 8601 datetime)
- F: `assigned_by` (Discord snowflake)
- G: `notes` (Free text)

**Primary Key**: Column A (`date`) - must be unique

**Operations**:
- Read: Get all rows, filter by date range
- Write: Update single row (by date) or batch update multiple rows
- Delete: Clear row (set columns B-F to empty)

---

### Sheet: "RecurringPatterns"

**Range**: `RecurringPatterns!A:I`

**Columns**:
- A: `pattern_id` (UUID)
- B: `host_discord_id` (Discord snowflake)
- C: `host_username` (Display name)
- D: `pattern_description` (Free text)
- E: `pattern_rule` (JSON string)
- F: `start_date` (YYYY-MM-DD)
- G: `end_date` (YYYY-MM-DD or empty)
- H: `created_at` (ISO 8601 datetime)
- I: `is_active` (TRUE/FALSE)

**Primary Key**: Column A (`pattern_id`) - must be unique

**Operations**:
- Read: Get all active patterns, filter by host
- Write: Insert new pattern row or update existing pattern
- Delete: Set `is_active` to FALSE (soft delete)

---

### Sheet: "AuditLog"

**Range**: `AuditLog!A:J`

**Columns**:
- A: `entry_id` (UUID)
- B: `timestamp` (ISO 8601 datetime)
- C: `action_type` (Enum string)
- D: `user_discord_id` (Discord snowflake)
- E: `target_user_discord_id` (Discord snowflake or empty)
- F: `event_date` (YYYY-MM-DD or empty)
- G: `recurring_pattern_id` (UUID or empty)
- H: `outcome` ("success" or "failure")
- I: `error_message` (Free text or empty)
- J: `metadata` (JSON string)

**Operations**:
- Read: Get recent entries (last N entries or date range)
- Write: Append new audit entry (always append, never update)

---

### Sheet: "Configuration"

**Range**: `Configuration!A:E`

**Columns**:
- A: `setting_key` (String, unique)
- B: `setting_value` (String, may be JSON)
- C: `setting_type` ("string", "integer", "boolean", "datetime", "json")
- D: `description` (Free text)
- E: `updated_at` (ISO 8601 datetime)

**Operations**:
- Read: Get all settings (load into memory at startup)
- Write: Update setting value and `updated_at` timestamp

---

## API Operations

### Read Operations

#### Get Schedule Events

**Endpoint**: `spreadsheets.values.get`

**Request**:
```python
service.spreadsheets().values().get(
    spreadsheetId=SPREADSHEET_ID,
    range='Schedule!A:G'
).execute()
```

**Response**:
```json
{
  "range": "Schedule!A1:G100",
  "majorDimension": "ROWS",
  "values": [
    ["date", "host_discord_id", "host_username", ...],  // Header row
    ["2025-11-11", "123456789012345678", "user#1234", ...],
    ...
  ]
}
```

**Quota Impact**: 1 read request per call

**Caching**: Cache response for `cache_ttl_seconds` (default 300s)

**Contract Test Requirements**:
- Verify correct range is requested
- Verify response parsing handles empty rows
- Verify caching works correctly

---

#### Get Recurring Patterns

**Endpoint**: `spreadsheets.values.get`

**Request**:
```python
service.spreadsheets().values().get(
    spreadsheetId=SPREADSHEET_ID,
    range='RecurringPatterns!A:I'
).execute()
```

**Response**: Same format as Schedule

**Quota Impact**: 1 read request per call

**Caching**: Cache response for `cache_ttl_seconds`

**Contract Test Requirements**:
- Verify active patterns filtered correctly (`is_active = TRUE`)
- Verify pattern rule JSON parsing

---

#### Get Configuration

**Endpoint**: `spreadsheets.values.get`

**Request**:
```python
service.spreadsheets().values().get(
    spreadsheetId=SPREADSHEET_ID,
    range='Configuration!A:E'
).execute()
```

**Response**: Same format as Schedule

**Quota Impact**: 1 read request per call (load once at startup, cache)

**Caching**: Cache until bot restart or `/sync` command

**Contract Test Requirements**:
- Verify configuration parsing by type
- Verify default values applied if setting missing

---

### Write Operations

#### Update Single Event Date

**Endpoint**: `spreadsheets.values.update`

**Request**:
```python
service.spreadsheets().values().update(
    spreadsheetId=SPREADSHEET_ID,
    range='Schedule!B2:G2',  # Row for specific date
    valueInputOption='USER_ENTERED',
    body={
        'values': [[host_discord_id, host_username, pattern_id, assigned_at, assigned_by, notes]]
    }
).execute()
```

**Quota Impact**: 1 write request per call

**Batch Alternative**: Use batch update for multiple dates (see below)

**Contract Test Requirements**:
- Verify date row lookup (find row by date value)
- Verify update only affects specified columns
- Verify read-after-write verification

---

#### Batch Update Multiple Events

**Endpoint**: `spreadsheets.values.batchUpdate`

**Request**:
```python
service.spreadsheets().values().batchUpdate(
    spreadsheetId=SPREADSHEET_ID,
    body={
        'valueInputOption': 'USER_ENTERED',
        'data': [
            {
                'range': 'Schedule!B5:G5',
                'values': [[host_discord_id, host_username, ...]]
            },
            {
                'range': 'Schedule!B10:G10',
                'values': [[host_discord_id, host_username, ...]]
            },
            ...
        ]
    }
).execute()
```

**Quota Impact**: 1 write request per batch (up to 100 ranges per batch)

**Batch Size**: Configurable via `max_batch_size` (default 100)

**Contract Test Requirements**:
- Verify batch size limits respected
- Verify all updates succeed or fail together
- Verify quota tracking increments correctly

---

#### Insert Recurring Pattern

**Endpoint**: `spreadsheets.values.append`

**Request**:
```python
service.spreadsheets().values().append(
    spreadsheetId=SPREADSHEET_ID,
    range='RecurringPatterns!A:I',
    valueInputOption='USER_ENTERED',
    insertDataOption='INSERT_ROWS',
    body={
        'values': [[pattern_id, host_discord_id, host_username, pattern_description, pattern_rule, start_date, end_date, created_at, is_active]]
    }
).execute()
```

**Quota Impact**: 1 write request per call

**Contract Test Requirements**:
- Verify pattern ID uniqueness
- Verify pattern rule JSON serialization

---

#### Update Configuration

**Endpoint**: `spreadsheets.values.update`

**Request**:
```python
# Find row by setting_key, update setting_value and updated_at
service.spreadsheets().values().update(
    spreadsheetId=SPREADSHEET_ID,
    range=f'Configuration!B{E}:E{E}',  # Row E found by setting_key
    valueInputOption='USER_ENTERED',
    body={
        'values': [[setting_value, setting_type, description, updated_at]]
    }
).execute()
```

**Quota Impact**: 1 write request per call

**Contract Test Requirements**:
- Verify setting key lookup
- Verify value type validation

---

#### Append Audit Entry

**Endpoint**: `spreadsheets.values.append`

**Request**:
```python
service.spreadsheets().values().append(
    spreadsheetId=SPREADSHEET_ID,
    range='AuditLog!A:J',
    valueInputOption='USER_ENTERED',
    insertDataOption='INSERT_ROWS',
    body={
        'values': [[entry_id, timestamp, action_type, user_discord_id, target_user_discord_id, event_date, recurring_pattern_id, outcome, error_message, metadata]]
    }
).execute()
```

**Quota Impact**: 1 write request per call

**Note**: Audit entries may be batched if multiple actions occur simultaneously

**Contract Test Requirements**:
- Verify audit entry format
- Verify JSON metadata serialization

---

## Quota Management

### Quota Limits

**Per User Per 100 Seconds**:
- Reads: 100 requests per 100 seconds
- Writes: 100 requests per 100 seconds

**Per Project Per Day**:
- Reads: 1000 requests per day (free tier)
- Writes: 1000 requests per day (free tier)

### Implementation Requirements (Principle I)

1. **Batching**: Batch multiple updates into single `batchUpdate` call
2. **Caching**: Cache reads for `cache_ttl_seconds` (default 300s)
3. **Exponential Backoff**: Retry with exponential backoff + jitter on 429 responses
4. **Quota Tracking**: Track usage and log at 80% threshold
5. **Graceful Degradation**: Serve from cache when quota exceeded

### Exponential Backoff

**Algorithm**:
```python
base_delay = 1  # seconds
max_delay = 60  # seconds
retry_count = 0

while retry_count < max_retries:
    try:
        # API call
        break
    except HttpError as e:
        if e.resp.status == 429:  # Rate limit
            delay = min(base_delay * (2 ** retry_count) + random_jitter(), max_delay)
            await asyncio.sleep(delay)
            retry_count += 1
        else:
            raise
```

**Contract Test Requirements**:
- Verify exponential backoff on 429 responses
- Verify jitter prevents thundering herd
- Verify max delay cap
- Verify quota tracking increments

---

## Error Handling

### Error Responses

**429 Too Many Requests**:
- Retry with exponential backoff
- Log quota usage
- Return user-friendly error if quota exhausted

**400 Bad Request**:
- Log error details
- Return user-friendly error with suggestions
- Validate inputs before API call

**401 Unauthorized**:
- Fail fast with clear error
- Check credentials configuration

**404 Not Found**:
- Verify spreadsheet ID and sheet names
- Return user-friendly error

**500 Internal Server Error**:
- Retry with exponential backoff (may be transient)
- Log error details
- Return user-friendly error

### Fallback Behavior (Principle II)

**When API Unavailable**:
1. Serve from cache if available
2. Show staleness warning: "⚠️ Data may be out of date. Last synced: [timestamp]"
3. Log error for monitoring
4. Continue serving cached data

**When Quota Exceeded**:
1. Log quota exhaustion
2. Serve from cache
3. Show warning: "⚠️ Google Sheets API quota exceeded. Using cached data."
4. Disable write operations until quota resets

**Contract Test Requirements**:
- Verify cache fallback on API failure
- Verify staleness warnings displayed
- Verify write operations disabled when quota exceeded
- Verify error messages are user-friendly

---

## Data Validation

### Input Validation (Before API Call)

- **Date Format**: Validate YYYY-MM-DD format
- **Discord ID**: Validate snowflake format (17-19 digits)
- **Pattern Rule**: Validate JSON format
- **Setting Types**: Validate type matches setting_type

### Output Validation (After API Response)

- **Row Count**: Verify expected number of rows returned
- **Column Count**: Verify expected number of columns
- **Data Types**: Verify types match expected format
- **Uniqueness**: Verify primary keys are unique

**Contract Test Requirements**:
- Verify input validation prevents invalid API calls
- Verify output validation catches API response issues
- Verify error handling for validation failures

---

## Testing Requirements

### Contract Tests

Contract tests MUST verify:
1. **Authentication**: Service account credentials work
2. **Sheet Structure**: All sheets exist with correct columns
3. **Read Operations**: Read operations return correct format
4. **Write Operations**: Write operations update correct cells
5. **Batch Operations**: Batch updates work correctly
6. **Quota Handling**: 429 responses handled with backoff
7. **Error Handling**: All error codes handled gracefully

### Integration Tests

Integration tests MUST verify:
1. **Real API Calls**: Test with actual Google Sheets (test spreadsheet)
2. **End-to-End**: Write → Read → Verify flow
3. **Cache Behavior**: Cache hits, misses, staleness
4. **Quota Limits**: Test approaching quota limits
5. **Failure Recovery**: Test recovery after API failures

### Mock Requirements

- Mock Google Sheets API responses for unit tests
- Use real API only in integration/contract tests
- Mock quota limit scenarios (429 responses)

---

## Performance Targets

- **Read Operations**: < 1 second (95th percentile)
- **Write Operations**: < 2 seconds (95th percentile)
- **Batch Operations**: < 5 seconds for 100 rows (95th percentile)
- **Cache Lookups**: < 100ms

**Contract Test Requirements**:
- Verify performance targets met
- Verify cache reduces API calls
- Verify batching improves throughput

