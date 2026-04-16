# Consolidate Announcement Channel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the two channel config fields (`schedule_channel_id`, `warnings_channel_id`) into a single `announcement_channel_id` so all bot-originated posts (daily warnings, future schedule/host announcements) go to one channel.

**Architecture:** Replace two `Optional[str]` fields on `Configuration` with one. Update the Google-Sheets-backed loader to prefer the new key and fall back to either old key during the deprecation window, so existing guilds don't lose their configured channel on first load after deploy. Update the setup wizard, `/config show`, and the daily-check posting path to reference the single new field. Drop the old keys from the dataclass, `config_meta`, and default sheet rows.

**Tech Stack:** Python 3.11+, discord.py, gspread (Google Sheets), pytest.

## Pre-execution decisions (confirm before starting)

- **New field name:** `announcement_channel_id` (neutral — covers both "today's host" announcements and "need a host" pings). If you prefer a different name (e.g. reuse `schedule_channel_id`), change every occurrence of `announcement_channel_id` in the plan before executing.
- **Migration strategy:** On load, prefer `announcement_channel_id` row; fall back to `warnings_channel_id` (the currently-functional one); then `schedule_channel_id`. Old rows stay in the sheet but are read-only fallback — they are ignored once the new row has a value. No write-back on load.
- **Scope:** This plan does *not* introduce a new "today's host" posting feature. It only consolidates the config. Content/routing differences (pinging vs. not pinging host roles) happen entirely in message bodies, not in channel routing.

---

## File Structure

**Modify:**
- `src/models/models.py` — swap two fields for one on `Configuration`
- `src/utils/config_meta.py` — swap two `SettingMeta` entries for one
- `src/services/sheets_service.py` — swap `DEFAULT_CONFIG_ROWS` entries; add fallback logic in `load_configuration`
- `src/services/discord_service.py` — daily_check reads `announcement_channel_id`
- `src/commands/setup_wizard.py` — channels step uses a single `_ChannelSelectForSetting`
- `src/commands/config_cmd.py` — `/config show` displays one "Announcement channel" line
- `README.md` — reference the new key
- `tests/test_config_meta.py` — extend `test_all_settings_have_required_fields` to cover `announcement_channel_id`

**Create:**
- `tests/test_sheets_config_loader.py` — covers the migration fallback behavior in `load_configuration` using a fake gspread worksheet

---

### Task 1: Swap channel fields on the Configuration dataclass

**Files:**
- Modify: `src/models/models.py:68-69`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_config_meta.py` (we'll add a fresh Configuration-focused test here to keep test layout simple):

```python
from src.models.models import Configuration


def test_configuration_has_single_announcement_channel_field():
    cfg = Configuration.default()
    assert hasattr(cfg, "announcement_channel_id")
    assert cfg.announcement_channel_id is None
    assert not hasattr(cfg, "schedule_channel_id")
    assert not hasattr(cfg, "warnings_channel_id")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config_meta.py::test_configuration_has_single_announcement_channel_field -v`
Expected: FAIL — `AssertionError: not hasattr(cfg, "schedule_channel_id")` (the two old fields still exist).

- [ ] **Step 3: Replace the two channel fields with one**

In `src/models/models.py`, replace lines 68–69:

```python
    schedule_channel_id: Optional[str] = None
    warnings_channel_id: Optional[str] = None
```

with:

```python
    announcement_channel_id: Optional[str] = None
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_config_meta.py::test_configuration_has_single_announcement_channel_field -v`
Expected: PASS.

- [ ] **Step 5: Run the full test suite to find other breakage**

Run: `pytest -x`
Expected: Other tests may fail because `config_meta`/`setup_wizard`/`config_cmd` still reference the old fields. That's expected — subsequent tasks fix those.

- [ ] **Step 6: Commit**

```bash
git add src/models/models.py tests/test_config_meta.py
git commit -m "refactor(config): replace two channel fields with announcement_channel_id"
```

---

### Task 2: Swap channel entries in config_meta

**Files:**
- Modify: `src/utils/config_meta.py:68-83`
- Modify: `tests/test_config_meta.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_config_meta.py`:

```python
def test_config_meta_has_single_announcement_channel_entry():
    assert "announcement_channel_id" in SETTINGS
    assert "schedule_channel_id" not in SETTINGS
    assert "warnings_channel_id" not in SETTINGS
    meta = SETTINGS["announcement_channel_id"]
    assert meta.group == "channels"
    assert meta.setting_type == "channel"
    assert meta.config_key == "announcement_channel_id"
    assert meta.sheets_type == "string"
```

- [ ] **Step 2: Run the failing test**

Run: `pytest tests/test_config_meta.py::test_config_meta_has_single_announcement_channel_entry -v`
Expected: FAIL — `"announcement_channel_id" not in SETTINGS`.

- [ ] **Step 3: Replace the two SettingMeta entries**

In `src/utils/config_meta.py`, replace the two entries at lines 68–83:

```python
    "schedule_channel_id": SettingMeta(
        group="channels",
        label="Schedule channel",
        setting_type="channel",
        config_key="schedule_channel_id",
        sheets_type="string",
        description="Channel where schedule posts are sent",
    ),
    "warnings_channel_id": SettingMeta(
        group="channels",
        label="Warnings channel",
        setting_type="channel",
        config_key="warnings_channel_id",
        sheets_type="string",
        description="Channel where warning posts are sent",
    ),
```

with a single entry:

```python
    "announcement_channel_id": SettingMeta(
        group="channels",
        label="Announcement channel",
        setting_type="channel",
        config_key="announcement_channel_id",
        sheets_type="string",
        description="Channel where the bot posts schedule announcements and host-needed warnings",
    ),
```

- [ ] **Step 4: Run the targeted test**

Run: `pytest tests/test_config_meta.py::test_config_meta_has_single_announcement_channel_entry -v`
Expected: PASS.

- [ ] **Step 5: Run the full config_meta test module**

Run: `pytest tests/test_config_meta.py -v`
Expected: All pass (the existing `test_all_settings_have_required_fields` still passes because `"channels"` remains a valid group and `"channel"` remains a valid type).

- [ ] **Step 6: Commit**

```bash
git add src/utils/config_meta.py tests/test_config_meta.py
git commit -m "refactor(config_meta): consolidate channel settings into announcement_channel_id"
```

---

### Task 3: Update sheets_service defaults and add migration fallback in load_configuration

**Files:**
- Modify: `src/services/sheets_service.py:75-76` (DEFAULT_CONFIG_ROWS)
- Modify: `src/services/sheets_service.py:358-382` (load_configuration)
- Create: `tests/test_sheets_config_loader.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sheets_config_loader.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.services.sheets_service import SheetsService


def _make_service_with_rows(rows: list[dict]) -> SheetsService:
    """Build a SheetsService instance with a fake worksheet returning `rows`."""
    svc = SheetsService.__new__(SheetsService)  # bypass __init__
    fake_ws = MagicMock()
    fake_ws.get_all_records.return_value = rows
    fake_ws.row_values.return_value = ["setting_key"]  # non-empty header short-circuit
    svc._get_or_create = MagicMock(return_value=fake_ws)  # type: ignore[attr-defined]
    return svc


def test_load_configuration_reads_announcement_channel_directly():
    svc = _make_service_with_rows([
        {"setting_key": "announcement_channel_id",
         "setting_value": "111", "setting_type": "string"},
    ])
    cfg = svc.load_configuration()
    assert cfg.announcement_channel_id == "111"


def test_load_configuration_falls_back_to_warnings_channel_id():
    svc = _make_service_with_rows([
        {"setting_key": "warnings_channel_id",
         "setting_value": "222", "setting_type": "string"},
    ])
    cfg = svc.load_configuration()
    assert cfg.announcement_channel_id == "222"


def test_load_configuration_falls_back_to_schedule_channel_id():
    svc = _make_service_with_rows([
        {"setting_key": "schedule_channel_id",
         "setting_value": "333", "setting_type": "string"},
    ])
    cfg = svc.load_configuration()
    assert cfg.announcement_channel_id == "333"


def test_load_configuration_prefers_announcement_over_legacy_keys():
    svc = _make_service_with_rows([
        {"setting_key": "schedule_channel_id",
         "setting_value": "333", "setting_type": "string"},
        {"setting_key": "warnings_channel_id",
         "setting_value": "222", "setting_type": "string"},
        {"setting_key": "announcement_channel_id",
         "setting_value": "111", "setting_type": "string"},
    ])
    cfg = svc.load_configuration()
    assert cfg.announcement_channel_id == "111"


def test_load_configuration_prefers_warnings_over_schedule_when_announcement_absent():
    svc = _make_service_with_rows([
        {"setting_key": "schedule_channel_id",
         "setting_value": "333", "setting_type": "string"},
        {"setting_key": "warnings_channel_id",
         "setting_value": "222", "setting_type": "string"},
    ])
    cfg = svc.load_configuration()
    assert cfg.announcement_channel_id == "222"


def test_load_configuration_none_when_no_channel_rows():
    svc = _make_service_with_rows([])
    cfg = svc.load_configuration()
    assert cfg.announcement_channel_id is None
```

- [ ] **Step 2: Run the failing tests**

Run: `pytest tests/test_sheets_config_loader.py -v`
Expected: All 6 tests FAIL — the loader still references the removed dataclass fields and doesn't know about `announcement_channel_id`.

- [ ] **Step 3: Update DEFAULT_CONFIG_ROWS**

In `src/services/sheets_service.py`, replace lines 75–76:

```python
    ("schedule_channel_id", "", "string", "Discord channel ID for schedule posts"),
    ("warnings_channel_id", "", "string", "Discord channel ID for warning posts"),
```

with:

```python
    ("announcement_channel_id", "", "string", "Discord channel ID where the bot posts schedule announcements and host-needed warnings"),
```

- [ ] **Step 4: Replace the channel-handling branch in load_configuration**

In `src/services/sheets_service.py`, replace the block at lines 378–379:

```python
                elif key in ("schedule_channel_id", "warnings_channel_id"):
                    setattr(config, key, val or None)
```

with:

```python
                elif key == "announcement_channel_id":
                    if val:
                        config.announcement_channel_id = val
                elif key in ("warnings_channel_id", "schedule_channel_id"):
                    # Legacy keys: used as fallback only if announcement_channel_id
                    # is not set after the full pass below. Stash them on locals.
                    pass
```

Then, after the `for row in rows:` loop (immediately before `return config`), insert the fallback pass:

```python
        if config.announcement_channel_id is None:
            legacy_order = ("warnings_channel_id", "schedule_channel_id")
            legacy: dict[str, str] = {}
            for row in rows:
                k = row.get("setting_key", "").strip()
                v = str(row.get("setting_value", "")).strip()
                if k in legacy_order and v:
                    legacy[k] = v
            for k in legacy_order:
                if k in legacy:
                    config.announcement_channel_id = legacy[k]
                    break
```

- [ ] **Step 5: Run the migration tests**

Run: `pytest tests/test_sheets_config_loader.py -v`
Expected: All 6 PASS.

- [ ] **Step 6: Run the full test suite**

Run: `pytest -x`
Expected: Remaining failures come from `setup_wizard.py`, `config_cmd.py`, and `discord_service.py` still referencing the removed fields. Next tasks fix those.

- [ ] **Step 7: Commit**

```bash
git add src/services/sheets_service.py tests/test_sheets_config_loader.py
git commit -m "feat(sheets): migrate legacy channel keys into announcement_channel_id on load"
```

---

### Task 4: Update discord_service daily_check to use announcement_channel_id

**Files:**
- Modify: `src/services/discord_service.py:111-113`

- [ ] **Step 1: Replace the channel-id lookup and log message**

In `src/services/discord_service.py`, replace lines 111–113:

```python
                channel_id = config.warnings_channel_id
                if not channel_id:
                    log.info("no warnings_channel_id configured; skipping post")
```

with:

```python
                channel_id = config.announcement_channel_id
                if not channel_id:
                    log.info("no announcement_channel_id configured; skipping post")
```

- [ ] **Step 2: Verify the file compiles / imports**

Run: `python -c "import src.services.discord_service"`
Expected: No `AttributeError` / `ImportError`.

- [ ] **Step 3: Commit**

```bash
git add src/services/discord_service.py
git commit -m "refactor(discord): route daily check posts to announcement_channel_id"
```

---

### Task 5: Update setup_wizard — single channel selector

**Files:**
- Modify: `src/commands/setup_wizard.py:57-66` (embed)
- Modify: `src/commands/setup_wizard.py:99-106` (summary embed)
- Modify: `src/commands/setup_wizard.py:129-133` (selectors for step 1)

- [ ] **Step 1: Replace the channels embed**

In `src/commands/setup_wizard.py`, replace lines 57–66 (the `_build_channels_embed` method body):

```python
    def _build_channels_embed(self) -> discord.Embed:
        cfg = self.cache.config
        embed = discord.Embed(
            title="Setup — Step 2/4: Channels",
            description="Where should I post?\n\nSelect channels below, or skip to keep current values.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Schedule channel", value=_channel_mention(cfg.schedule_channel_id))
        embed.add_field(name="Warnings channel", value=_channel_mention(cfg.warnings_channel_id))
        return embed
```

with:

```python
    def _build_channels_embed(self) -> discord.Embed:
        cfg = self.cache.config
        embed = discord.Embed(
            title="Setup — Step 2/4: Channel",
            description="Where should I post?\n\nSelect one channel below, or skip to keep the current value.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Announcement channel", value=_channel_mention(cfg.announcement_channel_id))
        return embed
```

- [ ] **Step 2: Replace the channels block in the summary embed**

In `src/commands/setup_wizard.py`, replace lines 99–106 (the `add_field(name="Channels", ...)` block):

```python
        embed.add_field(
            name="Channels",
            value=(
                f"Schedule: {_channel_mention(cfg.schedule_channel_id)}\n"
                f"Warnings: {_channel_mention(cfg.warnings_channel_id)}"
            ),
            inline=False,
        )
```

with:

```python
        embed.add_field(
            name="Channel",
            value=f"Announcement: {_channel_mention(cfg.announcement_channel_id)}",
            inline=False,
        )
```

- [ ] **Step 3: Replace the two channel selectors with one**

In `src/commands/setup_wizard.py`, replace lines 129–133 (the `elif self.step == 1:` block):

```python
        elif self.step == 1:
            embed = self._build_channels_embed()
            self.add_item(_ChannelSelectForSetting(self, "schedule_channel_id", placeholder="Select schedule channel..."))
            self.add_item(_ChannelSelectForSetting(self, "warnings_channel_id", placeholder="Select warnings channel..."))
            self.add_item(_NextButton(self, label="Next"))
```

with:

```python
        elif self.step == 1:
            embed = self._build_channels_embed()
            self.add_item(_ChannelSelectForSetting(self, "announcement_channel_id", placeholder="Select announcement channel..."))
            self.add_item(_NextButton(self, label="Next"))
```

- [ ] **Step 4: Run the setup wizard tests**

Run: `pytest tests/test_setup_wizard.py -v`
Expected: PASS (existing tests only check command name/description, so this should stay green).

- [ ] **Step 5: Verify the module still imports**

Run: `python -c "import src.commands.setup_wizard"`
Expected: No error.

- [ ] **Step 6: Commit**

```bash
git add src/commands/setup_wizard.py
git commit -m "refactor(wizard): collapse channels step to a single announcement selector"
```

---

### Task 6: Update /config show to display the single announcement channel

**Files:**
- Modify: `src/commands/config_cmd.py:73-75`

- [ ] **Step 1: Replace the Channels section in the show block**

In `src/commands/config_cmd.py`, replace lines 73–75:

```python
            "**Channels**",
            f"  Schedule channel: {_channel_mention(cfg.schedule_channel_id)}",
            f"  Warnings channel: {_channel_mention(cfg.warnings_channel_id)}",
```

with:

```python
            "**Channel**",
            f"  Announcement channel: {_channel_mention(cfg.announcement_channel_id)}",
```

- [ ] **Step 2: Run the config_cmd tests**

Run: `pytest tests/test_config_cmd.py -v`
Expected: PASS (existing tests only check group structure).

- [ ] **Step 3: Run the full test suite**

Run: `pytest`
Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/commands/config_cmd.py
git commit -m "refactor(config): show single announcement_channel_id in /config show"
```

---

### Task 7: Update README and verify

**Files:**
- Modify: `README.md:18`

- [ ] **Step 1: Replace the README reference**

In `README.md`, replace line 18:

```
Discord role IDs), and `warnings_channel_id` / `schedule_channel_id`.
```

with:

```
Discord role IDs), and `announcement_channel_id`.
```

- [ ] **Step 2: Search for any remaining references to old keys in src/**

Run: `rg -n "warnings_channel_id|schedule_channel_id" src/ tests/ README.md`
Expected: No matches in `src/` or `README.md`. Matches in `tests/test_sheets_config_loader.py` are legitimate (they test the legacy-key fallback). Matches in `docs/`, `specs/`, and the older plan file under `docs/superpowers/plans/` are historical and should be left alone.

- [ ] **Step 3: Run the full test suite one more time**

Run: `pytest`
Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): reference announcement_channel_id as the single channel key"
```

---

## Post-implementation notes (for future follow-up, not this plan)

- Once the new key has been live for one release cycle, delete the legacy fallback in `load_configuration` and simplify the branch to `elif key == "announcement_channel_id":`.
- Old sheet rows (`warnings_channel_id`, `schedule_channel_id`) remain in users' Configuration sheets. They are harmless but can be deleted manually. A follow-up plan could add a one-shot cleanup that deletes them on first load once a value has been migrated.
- This plan intentionally does *not* introduce the "today's host" announcement message. When that feature is built, it will post to `config.announcement_channel_id` with no role pings; the existing daily-check code already pings host/admin roles only for urgent warnings.

---

## Self-review checklist (completed during writing)

- [x] **Spec coverage:** Every touchpoint from the discussion (model, config_meta, sheets defaults, sheets loader, discord_service, setup_wizard, config_cmd show, README) has a task.
- [x] **Placeholder scan:** No TBDs, no "handle edge cases", no "similar to Task N" without code. All steps show exact code.
- [x] **Type consistency:** `announcement_channel_id` (snake_case, singular) used everywhere. `SettingMeta` and `Optional[str]` usages match the existing codebase.
- [x] **Testing strategy:** Config-shape tests added in `test_config_meta.py`. Migration behavior covered by a new dedicated loader test module. Existing tests for wizard/config_cmd are kept green (they don't assert on channel fields).
- [x] **Migration safety:** Legacy rows are read as fallback; no write-back; precedence documented (`announcement > warnings > schedule`).
