# Test Coverage Expansion Plan

**Repo:** `language-exchange-bot` — a Discord bot managing host volunteering for recurring meetups, backed by Google Sheets.

**Goal:** Expand the unit-test suite beyond what exists today. A first wave (108 tests) covers utilities, models, cache_service, warning_service, and shallow command structure. This plan covers the next waves.

---

## Ground rules

**Test framework:** `pytest` with `pytest-asyncio` in `strict` mode (config in `pyproject.toml`).

**Run tests:**
```bash
python3 -m pytest tests/ -v
```

**Install dev deps:**
```bash
pip install -r requirements-dev.txt
```

**Lint scope:** CI's `ruff` runs against `src/` only. Tests are expected to be ruff-clean too — run `ruff check tests/ --fix` after writing.

**Existing conventions (follow these):**
- `from __future__ import annotations` at top of every test file.
- Use `MagicMock` for sheets and cache, `AsyncMock` for `cache.refresh`.
- For Discord objects use `MagicMock(spec=discord.Member)` / `spec=discord.User`.
- Patch time with `patch("module.today_la", return_value=date(YYYY, M, D))` — never rely on real clock.
- `@pytest.mark.asyncio` for coroutine tests.
- Fixtures live at the top of each test file; no project-wide `conftest.py` yet (add one only if shared fixtures appear 3+ times).
- Keep each test focused on a single behavior; name after what is being verified.

**Do NOT:**
- Modify `src/` code to make testing easier unless you also flag it as a design issue. The goal is test coverage, not refactor.
- Use real gspread/Google Sheets. Mock `SheetsService` and its methods.
- Add integration tests that hit the Discord API or the Sheets API.

**Existing example patterns to mimic:**
- `tests/test_cache_service.py` — async fixture + `MagicMock` sheets, good template for service tests.
- `tests/test_warning_service.py` — patches `today_la` for deterministic time.
- `tests/test_auth.py` — Discord Member/User mocking with `spec=`.
- `tests/test_help_coverage.py` — builds a real `app_commands.CommandTree` from mocked deps.

---

## Wave 1 — Easy, high-signal command-handler tests

These command handlers have branching logic that can be exercised with simple mocks. Each new test file should follow the `test_help_coverage.py` / `test_cache_service.py` style.

### 1.1 `tests/test_schedule_cmd.py` → covers `src/commands/schedule.py`

The `/schedule` command applies role checks, filters events by week/date, truncates output, and formats a timeline view.

**Add tests for:**
- Role-based branching around lines 27–40 (non-member rejected, host sees timeline, admin sees full view — depending on current logic, read the file first).
- Date parsing of the optional `date` argument (good value + bad value).
- Week boundary logic (lines ~58–61): passing `weeks=0`, `weeks=1`, default weeks.
- Output truncation at ~line 98–100 (when event list exceeds max length, does it truncate cleanly?).
- Empty schedule case (no events in window).

**How to test:** Mock `cache.all_events()` to return `EventDate` lists you construct. Patch `today_la`. Assert on the embed/response string that the command builds — look at how existing tests build a `CommandTree` to get at the callback, or invoke the command's coroutine directly with a mocked `discord.Interaction`.

### 1.2 `tests/test_sync_cmd.py` → covers `src/commands/sync.py`

- Happy path: cache gets invalidated, refresh called, audit appended.
- Exception path: if `cache.refresh` raises, error is handled and audit records failure outcome.
- Permission check (admin-only).

### 1.3 `tests/test_reset_cmd.py` → covers `src/commands/reset.py`

- `_ConfirmReset` view: cancel callback does nothing destructive; confirm callback invalidates cache, refreshes, appends audit.
- Invoker check (line ~28): a user who didn't initiate the command cannot click confirm.

### 1.4 `tests/test_sheet_cmd.py` → covers `src/commands/sheet.py`

- `sheet_url()` reads `GOOGLE_SHEETS_SPREADSHEET_ID` env var and returns the expected URL.
- Missing env var path.

Use `monkeypatch.setenv` / `monkeypatch.delenv`.

### 1.5 `tests/test_warnings_cmd.py` → covers `src/commands/warnings_cmd.py`

- Role check (non-member rejected).
- Happy path: calls `WarningService.check()`, formats with correct icons (`🚨` urgent / `⚠️` passive).
- No warnings case produces an "all clear" style response.

---

## Wave 2 — config_cmd subcommand validation (high value, medium effort)

Target: `src/commands/config_cmd.py` (~lines 35–292). The existing `tests/test_config_cmd.py` only asserts the subgroup names. Replace it (or add a new `test_config_cmd_handlers.py`) covering the subcommand handlers.

For each subcommand handler:

### 2.1 `config show` (~line 36–77)
- Formats role mentions and channel references correctly.
- Handles missing/None channel IDs gracefully.
- Shows all 7+ settings fields.

### 2.2 Warning subcommands (`passive_days`, `urgent_days`)
- Valid value → calls `sheets.update_configuration` with correct args, refreshes cache.
- Out-of-range value → error message, no sheet write.
- Non-integer value → error message.

### 2.3 Schedule subcommands (`window_weeks`, `daily_check_time`, `daily_check_timezone`)
- Each type (integer, time, timezone) has a valid + invalid case.
- Timezone autocomplete (line 177–182): returns IANA zones matching the prefix.

### 2.4 Channels subcommands (`schedule`, `warnings`)
- Setting a channel writes channel ID to sheets.
- Clearing (empty/null) works.

### 2.5 Roles subcommands (`add`, `remove` across member/host/admin)
- Adding a role ID appends to the correct list; duplicates are not double-added.
- Removing a role that isn't present is a no-op with a reasonable message.
- Adding/removing writes the full JSON array back via `sheets.update_configuration`.

**Common fixtures:**
```python
@pytest.fixture
def sheets(): return MagicMock()

@pytest.fixture
def cache():
    c = MagicMock()
    c.config = Configuration.default()
    c.refresh = AsyncMock()
    return c
```

Invoke handlers by extracting them from the group: `group = build_group(sheets, cache); cmd = group.get_command("warnings").get_command("passive_days")` — then call `cmd.callback(interaction, value)` with a mocked interaction.

**Interaction mock helper (add to a per-file helper or conftest):**
```python
def make_interaction(user_id=1, role_ids=(), guild=True):
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = user_id
    interaction.user.roles = [MagicMock(id=r) for r in role_ids]
    interaction.guild = MagicMock() if guild else None
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction
```

---

## Wave 3 — volunteer / unvolunteer command logic

### 3.1 `tests/test_volunteer_cmd.py` → covers `src/commands/volunteer.py`

- `open_date_autocomplete` (lines 35–54): returns ≤25 items, filters by prefix, sorts chronologically.
- `volunteer_date` (lines 59–124):
  - Happy path: date in future, not already assigned → creates assignment, audit appended, cache updated.
  - Date in the past → rejected.
  - Date already assigned to someone else → rejected (or confirmation flow, whichever the code does — read first).
  - Exception in sheets write is caught and logged.
- `_ConfirmView` (lines 179–267):
  - Invoker-only check (line 199).
  - Confirm callback: creates `RecurringPattern` with a UUID, serializes to JSON, writes via `sheets.append_pattern`.
  - Error path: `sheets` raises → view shows error.

### 3.2 `tests/test_unvolunteer_cmd.py` → covers `src/commands/unvolunteer.py`

- `user_dates_autocomplete` (lines 31–56): pulls `target_id` from `interaction.data`, filters assigned dates for that user.
- `unvolunteer_date` (lines 61–119): clears assignment, triggers warning check integration.
- `unvolunteer_recurring` (lines 123–170): deactivates pattern, deletes future rows, invalidates cache.

---

## Wave 4 — setup_wizard behavior

Target: `src/commands/setup_wizard.py` (~lines 155–305). Currently only the command name/description are tested.

### 4.1 `tests/test_setup_wizard_flow.py`

- Owner check: non-owner → rejected with clear message.
- Guild check: DM invocation → rejected.
- `SetupWizardView` step progression: next/back buttons advance/regress the step index, view updates embed.
- Modal validation: submit with 5 fields → aggregates all errors if any invalid, does not write partial state.
- Successful modal: writes each field via `sheets.update_configuration`, refreshes cache.

**Note:** `discord.ui.Modal` and `Button` instances can be tested by calling their `callback` directly with a mocked interaction. Look at how existing Discord tests build `MagicMock(spec=discord.Interaction)` and attach `response.send_message = AsyncMock()`.

---

## Wave 5 — sheets_service logic (medium-hard, high value)

Target: `src/services/sheets_service.py`. Skip `__init__` (env-var + gspread auth). Focus on methods that take a `gspread.Worksheet` or use `self.spreadsheet`.

**Pattern:** construct a `SheetsService` via `__new__` to bypass `__init__`, then attach a mocked `spreadsheet`:
```python
svc = SheetsService.__new__(SheetsService)
svc.spreadsheet = MagicMock()
svc.write_lock = asyncio.Lock()
ws = MagicMock()
svc.spreadsheet.worksheet.return_value = ws
```

### 5.1 `tests/test_sheets_service.py`

- `_get_or_create` (line 77–87): existing worksheet reused; missing worksheet → `add_worksheet` called with correct title and headers appended; empty worksheet → headers appended.
- `ensure_sheets` (line 89–97): iterates four sheets; for Configuration, only missing keys are appended (set up `config_ws.get_all_values.return_value` with a subset).
- `load_configuration` (line 100–124): type coercion for each category — integers, JSON arrays, strings, optional channel IDs; malformed JSON logs and skips but does not crash.
- `update_configuration` (line 126–134): existing key → `ws.update` with correct range; missing key → `ws.append_row`.
- `load_schedule` (line 137–165): valid row → `EventDate`; bad date string → row skipped; bad `assigned_at` → event kept but `assigned_at` is None.
- `_find_schedule_row` (line 167–172): returns 1-based row index or None.
- `upsert_schedule_row` (line 174–190): new vs existing row paths.
- `clear_schedule_assignment` (line 192–199): returns True on clear, False when row not found.
- `delete_future_pattern_rows` (line 201–216): clears only rows matching pattern_id AND date ≥ from_date.
- `load_patterns` (line 219–249): parses `is_active` TRUE/FALSE/missing correctly; bad start_date skips row; missing end_date is None.
- `append_pattern` (line 251–263): row values are serialized in correct order and format.
- `deactivate_pattern` (line 265–272): found vs not found paths.
- `append_audit` (line 275–288): metadata empty vs non-empty path.

---

## Wave 6 — discord_service daily loop (optional, hardest)

Target: `src/services/discord_service.py` lines 98–132. Requires mocking `discord.ext.tasks.Loop` or refactoring `_start_daily_check` to expose the inner coroutine. Read the file first — consider whether restructuring the inner function to be a module-level helper would make it testable without harming the design. If yes, flag in your report; don't refactor unilaterally.

If refactoring is off the table, skip this wave or cover only the string formatting of the warning message (role mentions, icons, urgent filtering) by extracting those into a helper and testing the helper.

---

## Side task: investigate async executor inconsistency

While reading `src/commands/sync.py` (~line 22) and comparing to `src/commands/volunteer.py` (~line 106–114), note that `sync.py` calls `sheets.append_audit(...)` synchronously in an async handler, while `volunteer.py` wraps the same call in `loop.run_in_executor`. This is either (a) an intentional difference because `sync.py` is an admin command run rarely or (b) a latent bug that could block the event loop if gspread stalls.

**Deliverable (only if investigating):** a short note in `docs/` or a GitHub issue describing the finding. Do not "fix" it as part of test work.

---

## Acceptance criteria

- All new tests pass locally: `python3 -m pytest tests/ -v` exits 0.
- `ruff check src tests` exits 0.
- CI (`.github/workflows/deploy.yml`) continues to pass. The `test` job already runs `pytest tests/ -v`; no workflow changes should be needed.
- Each new test file targets one module and has a focused scope (no cross-module integration tests).
- Total test count increases meaningfully. Aim for:
  - Wave 1 → +20–30 tests
  - Wave 2 → +30–40 tests
  - Wave 3 → +20–30 tests
  - Wave 4 → +10–15 tests
  - Wave 5 → +25–35 tests
  - Wave 6 → optional

## Out of scope

- End-to-end or integration tests (real Discord / real Sheets).
- Refactoring production code unless a test cannot possibly be written without it — and even then, flag it rather than silently refactor.
- Performance benchmarks.
- Coverage reporting setup (can be a follow-up).

---

## Suggested execution order

1. Wave 1 (easy, confidence-building).
2. Wave 2 (high value, same mocking pattern).
3. Wave 3 (core workflow).
4. Wave 5 (service layer correctness).
5. Wave 4 (wizard UI — trickiest mocking).
6. Wave 6 (optional; only if the daily-check loop has a history of regressions).

Commit after each wave. Keep commit messages in the project's style (e.g. `test: add command handler coverage for schedule/sync/reset`).
