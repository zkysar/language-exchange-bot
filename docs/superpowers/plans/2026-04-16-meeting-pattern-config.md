# Meeting Pattern Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `meeting_pattern` config setting (e.g., `"every wednesday"`) so the `/hosting signup` date autocomplete only surfaces days your exchange actually meets.

**Architecture:** `meeting_pattern` is a new optional string field on `Configuration`, validated by the existing `parse_pattern()` utility. When set, `_signup_date_autocomplete` generates the set of valid meeting dates from the pattern and filters the autocomplete list to only those days. The setup wizard gains a dedicated "Set meeting pattern" button in Step 3 (a separate modal — the existing `_ScheduleModal` is already at Discord's 5-field limit). The setting is also reachable via the existing `/config` command flow.

**Tech Stack:** Python 3.12, discord.py (app_commands, ui.Modal), gspread, pytest, dateutil

---

## File Map

| File | Change |
|---|---|
| `src/models/models.py` | Add `meeting_pattern: Optional[str] = None` to `Configuration` |
| `src/utils/config_meta.py` | Add `"pattern"` setting type + `meeting_pattern` entry in `SETTINGS`; update `validate_setting` |
| `src/services/sheets_service.py` | Load `meeting_pattern` as a string key in `load_configuration` |
| `src/commands/hosting.py` | Filter `_signup_date_autocomplete` to meeting dates when pattern is set |
| `src/commands/setup_wizard.py` | Add `_MeetingPatternModal` + "Set meeting pattern" button to Step 3 |
| `tests/test_models.py` | Assert `meeting_pattern` default is `None` and can be set |
| `tests/test_config_meta.py` | Update allowed `setting_type` set; add `meeting_pattern` validate tests |
| `tests/test_hosting_cmd.py` | Autocomplete returns all dates when no pattern; only Wednesdays when set |

---

### Task 1: Add `meeting_pattern` to the `Configuration` model

**Files:**
- Modify: `src/models/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Open `tests/test_models.py` and append:

```python
from src.models.models import Configuration


def test_configuration_meeting_pattern_default_none():
    cfg = Configuration.default()
    assert cfg.meeting_pattern is None


def test_configuration_meeting_pattern_can_be_set():
    cfg = Configuration(meeting_pattern="every wednesday")
    assert cfg.meeting_pattern == "every wednesday"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_models.py::test_configuration_meeting_pattern_default_none -v
```

Expected: `FAILED` — `Configuration` has no attribute `meeting_pattern`

- [ ] **Step 3: Add field to `Configuration`**

In `src/models/models.py`, add one line after `warnings_channel_id`:

```python
    warnings_channel_id: Optional[str] = None
    meeting_pattern: Optional[str] = None   # <-- add this
    cache_ttl_seconds: int = 300
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected: all tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/models/models.py tests/test_models.py
git commit -m "feat: add meeting_pattern field to Configuration model"
```

---

### Task 2: Register `meeting_pattern` in `config_meta.py`

**Files:**
- Modify: `src/utils/config_meta.py`
- Test: `tests/test_config_meta.py`

- [ ] **Step 1: Write the failing tests**

Open `tests/test_config_meta.py`. The existing test `test_all_settings_have_required_fields` asserts `setting_type in ("integer", "time", "timezone", "channel")` — that line will need updating. Add these tests (and update that assertion):

```python
def test_all_settings_have_required_fields():
    for key, meta in SETTINGS.items():
        assert isinstance(meta, SettingMeta), f"{key} is not SettingMeta"
        assert meta.group in ("warnings", "schedule", "channels", "roles")
        assert meta.label
        assert meta.config_key
        assert meta.setting_type in ("integer", "time", "timezone", "channel", "pattern")


def test_meeting_pattern_in_settings():
    assert "meeting_pattern" in SETTINGS
    meta = SETTINGS["meeting_pattern"]
    assert meta.group == "schedule"
    assert meta.setting_type == "pattern"


def test_validate_meeting_pattern_valid():
    ok, val, err = validate_setting("meeting_pattern", "every wednesday")
    assert ok is True
    assert val == "every wednesday"
    assert err is None


def test_validate_meeting_pattern_valid_nth():
    ok, val, err = validate_setting("meeting_pattern", "every 2nd tuesday")
    assert ok is True


def test_validate_meeting_pattern_invalid():
    ok, val, err = validate_setting("meeting_pattern", "not a real pattern")
    assert ok is False
    assert err is not None


def test_validate_meeting_pattern_empty_clears():
    ok, val, err = validate_setting("meeting_pattern", "")
    assert ok is True
    assert val == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config_meta.py::test_meeting_pattern_in_settings -v
```

Expected: `FAILED` — `"meeting_pattern" not in SETTINGS`

- [ ] **Step 3: Add `meeting_pattern` to `SETTINGS` and handle `"pattern"` type in `validate_setting`**

In `src/utils/config_meta.py`, add the import at the top:

```python
from src.utils.pattern_parser import parse_pattern
```

Then add to the `SETTINGS` dict (inside the dict literal, after `warnings_channel_id`):

```python
    "meeting_pattern": SettingMeta(
        group="schedule",
        label="Meeting pattern",
        setting_type="pattern",
        config_key="meeting_pattern",
        sheets_type="string",
        description="Recurrence pattern for when the exchange meets (e.g. 'every wednesday', 'every 2nd tuesday'). Leave blank to allow any date.",
    ),
```

Then in `validate_setting`, add a new branch before the final `return False`:

```python
    if meta.setting_type == "pattern":
        if value == "":
            return True, "", None
        try:
            parse_pattern(value)
        except ValueError as e:
            return False, None, f"`{meta.label}`: {e}"
        return True, value, None
```

- [ ] **Step 4: Run all config_meta tests**

```bash
pytest tests/test_config_meta.py -v
```

Expected: all `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/utils/config_meta.py tests/test_config_meta.py
git commit -m "feat: add meeting_pattern setting type and registration"
```

---

### Task 3: Load `meeting_pattern` from Google Sheets

**Files:**
- Modify: `src/services/sheets_service.py`
- Test: `tests/test_sheets_service.py`

- [ ] **Step 1: Write the failing test**

Open `tests/test_sheets_service.py` and search for an existing test that exercises `load_configuration`. Add (or append to that test group):

```python
def test_load_configuration_reads_meeting_pattern(sheets_service_with_data):
    """meeting_pattern is loaded as a plain string."""
    # sheets_service_with_data is whatever fixture the file already uses;
    # if one doesn't exist, mock directly as shown below.
    from unittest.mock import MagicMock, patch
    from src.services.sheets_service import SheetsService

    ws = MagicMock()
    ws.get_all_records.return_value = [
        {"setting_key": "meeting_pattern", "setting_value": "every wednesday",
         "setting_type": "string", "description": "", "updated_at": ""},
    ]
    svc = MagicMock(spec=SheetsService)
    svc._get_or_create = MagicMock(return_value=ws)
    svc.load_configuration = SheetsService.load_configuration.__get__(svc)
    cfg = svc.load_configuration()
    assert cfg.meeting_pattern == "every wednesday"
```

> **Note:** Check the existing `test_sheets_service.py` fixture style before writing this — if there's a `make_service()` or `sheets` fixture, use it instead of the manual mock above.

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_sheets_service.py -k "meeting_pattern" -v
```

Expected: `FAILED` — `load_configuration` doesn't set `meeting_pattern`

- [ ] **Step 3: Add `meeting_pattern` to the string-key block in `load_configuration`**

In `src/services/sheets_service.py`, locate the `elif key in ("daily_check_time", "daily_check_timezone"):` branch (around line 375) and extend it:

```python
                elif key in ("daily_check_time", "daily_check_timezone", "meeting_pattern"):
                    if val:
                        setattr(config, key, val)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_sheets_service.py -v
```

Expected: all `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/services/sheets_service.py tests/test_sheets_service.py
git commit -m "feat: load meeting_pattern from Configuration sheet"
```

---

### Task 4: Filter `/hosting signup` date autocomplete

**Files:**
- Modify: `src/commands/hosting.py`
- Test: `tests/test_hosting_cmd.py`

The key function is `_signup_date_autocomplete` (line 125–144). When `cache.config.meeting_pattern` is set, only dates that fall on a meeting day should appear.

- [ ] **Step 1: Write the failing tests**

Open `tests/test_hosting_cmd.py` and append:

```python
from src.commands.hosting import _signup_date_autocomplete
from src.models.models import Configuration
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock


def _make_cache_for_autocomplete(meeting_pattern: str | None = None):
    cache = MagicMock()
    cache.config = Configuration.default()
    cache.config.meeting_pattern = meeting_pattern
    cache.refresh = AsyncMock()
    cache.all_events = MagicMock(return_value=[])
    return cache


@pytest.mark.asyncio
async def test_autocomplete_no_pattern_returns_all_days():
    cache = _make_cache_for_autocomplete(meeting_pattern=None)
    interaction = MagicMock(spec=discord.Interaction)
    choices = await _signup_date_autocomplete(interaction, "", cache)
    assert len(choices) == 25  # hits the cap


@pytest.mark.asyncio
async def test_autocomplete_with_wednesday_pattern_returns_only_wednesdays():
    cache = _make_cache_for_autocomplete(meeting_pattern="every wednesday")
    interaction = MagicMock(spec=discord.Interaction)
    choices = await _signup_date_autocomplete(interaction, "", cache)
    assert len(choices) > 0
    for choice in choices:
        d = date.fromisoformat(choice.value)
        assert d.weekday() == 2, f"{d} is not a Wednesday"


@pytest.mark.asyncio
async def test_autocomplete_with_invalid_pattern_falls_back_to_all_days():
    cache = _make_cache_for_autocomplete(meeting_pattern="not parseable garbage")
    interaction = MagicMock(spec=discord.Interaction)
    choices = await _signup_date_autocomplete(interaction, "", cache)
    assert len(choices) == 25  # graceful fallback
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_hosting_cmd.py::test_autocomplete_with_wednesday_pattern_returns_only_wednesdays -v
```

Expected: `FAILED` — autocomplete returns non-Wednesday dates

- [ ] **Step 3: Update `_signup_date_autocomplete` to filter by pattern**

Replace the body of `_signup_date_autocomplete` in `src/commands/hosting.py`:

```python
async def _signup_date_autocomplete(
    interaction: discord.Interaction, current: str, cache: CacheService
) -> List[app_commands.Choice[str]]:
    await cache.refresh()
    today = today_la()
    horizon = today + timedelta(weeks=12)
    events = {e.date: e for e in cache.all_events()}

    meeting_dates: set | None = None
    if cache.config.meeting_pattern:
        try:
            parsed = parse_pattern(cache.config.meeting_pattern)
            meeting_dates = set(generate_dates(parsed, today, months=3))
        except ValueError:
            pass  # malformed config — fall back to all dates

    choices: List[app_commands.Choice[str]] = []
    for i in range((horizon - today).days + 1):
        d = today + timedelta(days=i)
        if meeting_dates is not None and d not in meeting_dates:
            continue
        ev = events.get(d)
        if ev and ev.is_assigned:
            continue
        label = format_display(d)
        if current and current.lower() not in label.lower() and current not in format_date(d):
            continue
        choices.append(app_commands.Choice(name=label, value=format_date(d)))
        if len(choices) >= 25:
            break
    return choices
```

- [ ] **Step 4: Run all hosting tests**

```bash
pytest tests/test_hosting_cmd.py -v
```

Expected: all `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/commands/hosting.py tests/test_hosting_cmd.py
git commit -m "feat: filter hosting date autocomplete to meeting days when pattern is set"
```

---

### Task 5: Expose `meeting_pattern` in the setup wizard

**Files:**
- Modify: `src/commands/setup_wizard.py`
- Test: `tests/test_setup_wizard.py` or `tests/test_setup_wizard_flow.py`

The existing `_ScheduleModal` already has 5 fields (Discord's hard limit). Add a separate `_MeetingPatternModal` and a "Set meeting pattern" button alongside the existing "Customize" button in Step 3.

- [ ] **Step 1: Write the failing test**

Open `tests/test_setup_wizard.py` (or `tests/test_setup_wizard_flow.py` — whichever has the Step 3 tests) and append:

```python
from src.commands.setup_wizard import SetupWizardView, _MeetingPatternModal


def test_meeting_pattern_modal_exists():
    """_MeetingPatternModal is importable and is a discord.ui.Modal subclass."""
    import discord
    assert issubclass(_MeetingPatternModal, discord.ui.Modal)


def test_step3_embed_shows_meeting_pattern(wizard):
    """Step 3 embed includes the current meeting_pattern value."""
    wizard.cache.config.meeting_pattern = "every wednesday"
    embed = wizard._build_schedule_embed()
    field_values = [f.value for f in embed.fields]
    assert any("every wednesday" in v for v in field_values)


def test_step3_embed_shows_not_set_when_no_pattern(wizard):
    wizard.cache.config.meeting_pattern = None
    embed = wizard._build_schedule_embed()
    field_values = [f.value for f in embed.fields]
    assert any("not set" in v.lower() for v in field_values)
```

> **Note:** Check the existing fixture for `wizard` — if it doesn't exist, create a small one that builds a `SetupWizardView` with mocked `sheets`, `cache`, and `interaction`.

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_setup_wizard.py::test_meeting_pattern_modal_exists -v
```

Expected: `FAILED` — `_MeetingPatternModal` not importable

- [ ] **Step 3: Add `_MeetingPatternModal` and button to `setup_wizard.py`**

After the `_CustomizeButton` class, add:

```python
class _MeetingPatternModal(ui.Modal, title="Set Meeting Pattern"):
    pattern = ui.TextInput(
        label="Meeting pattern",
        placeholder="e.g. every wednesday, every 2nd tuesday",
        max_length=80,
        required=False,
    )

    def __init__(self, wizard: SetupWizardView) -> None:
        super().__init__()
        self.wizard = wizard
        cfg = wizard.cache.config
        self.pattern.default = cfg.meeting_pattern or ""

    async def on_submit(self, interaction: discord.Interaction) -> None:
        value = self.pattern.value.strip()
        ok, val, err = validate_setting("meeting_pattern", value)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return
        self.wizard.sheets.update_configuration("meeting_pattern", val, type_="string")
        await self.wizard.cache.refresh(force=True)
        await self.wizard._show_step(interaction)


class _MeetingPatternButton(ui.Button):
    def __init__(self, wizard: SetupWizardView) -> None:
        super().__init__(style=discord.ButtonStyle.secondary, label="Set meeting pattern")
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(_MeetingPatternModal(self.wizard))
```

Then add the import at the top of the file (already imported `validate_setting` — if not, add it):

```python
from src.utils.config_meta import SETTINGS, validate_setting
```

Then update `_build_schedule_embed` to show the current pattern. Add a new field after the existing ones:

```python
    def _build_schedule_embed(self) -> discord.Embed:
        cfg = self.cache.config
        embed = discord.Embed(
            title="Setup — Step 3/4: Schedule Settings",
            description="How should warnings work?\n\nUse defaults or customize each setting.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Daily check time", value=cfg.daily_check_time, inline=True)
        embed.add_field(name="Timezone", value=cfg.daily_check_timezone, inline=True)
        embed.add_field(name="Passive warning days", value=str(cfg.warning_passive_days), inline=True)
        embed.add_field(name="Urgent warning days", value=str(cfg.warning_urgent_days), inline=True)
        embed.add_field(name="Schedule window", value=f"{cfg.schedule_window_weeks} weeks", inline=True)
        embed.add_field(
            name="Meeting pattern",
            value=cfg.meeting_pattern or "*not set — all dates shown*",
            inline=True,
        )
        return embed
```

Then in `_show_step`, update the `elif self.step == 2:` branch to add the new button:

```python
        elif self.step == 2:
            embed = self._build_schedule_embed()
            self.add_item(_MeetingPatternButton(self))
            self.add_item(_CustomizeButton(self))
            self.add_item(_NextButton(self, label="Use defaults & finish"))
```

Also update `_build_summary_embed` to show the pattern:

```python
        embed.add_field(
            name="Schedule",
            value=(
                f"Check time: {cfg.daily_check_time} ({cfg.daily_check_timezone})\n"
                f"Passive warning: {cfg.warning_passive_days} days\n"
                f"Urgent warning: {cfg.warning_urgent_days} days\n"
                f"Window: {cfg.schedule_window_weeks} weeks\n"
                f"Meeting pattern: {cfg.meeting_pattern or '*not set*'}"
            ),
            inline=False,
        )
```

- [ ] **Step 4: Run all setup wizard tests**

```bash
pytest tests/test_setup_wizard.py tests/test_setup_wizard_flow.py -v
```

Expected: all `PASSED`

- [ ] **Step 5: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all `PASSED`. Fix any failures before continuing.

- [ ] **Step 6: Run ruff**

```bash
ruff check src/ tests/
```

Expected: no errors. Fix any issues.

- [ ] **Step 7: Commit**

```bash
git add src/commands/setup_wizard.py tests/test_setup_wizard.py tests/test_setup_wizard_flow.py
git commit -m "feat: add meeting pattern step to setup wizard"
```

---

## Post-implementation checklist

- [ ] **Sheet note:** The Google Sheet's `Configuration` tab does not auto-populate this key. After deploying, run `/config schedule` → set `meeting_pattern`, OR manually add a row: `meeting_pattern | every wednesday | string | When the exchange meets`.
- [ ] **README/spec drift:** If `README.md` or the spec lists config keys, add `meeting_pattern` there. (Per CLAUDE.md, call out drift — don't silently skip it.)
