# Config Command & Setup Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the role-only `/setup` command with a general `/config` command group (granular settings with validation/autocomplete) and a `/setup` wizard (guided first-time configuration).

**Architecture:** A shared settings registry (`src/utils/config_meta.py`) defines all exposed settings with their types, validation rules, and labels. `/config` subcommands and the `/setup` wizard both reference this registry. Existing `SheetsService.update_configuration()` and `CacheService.refresh()` are reused unchanged.

**Tech Stack:** Python 3.11+, discord.py (app_commands, ui.View, ui.Modal, ui.RoleSelect, ui.ChannelSelect), zoneinfo

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/utils/config_meta.py` | Create | Settings registry with types, validation, labels |
| `src/commands/config_cmd.py` | Create | `/config` command group (show, warnings, schedule, channels, roles) |
| `src/commands/setup_wizard.py` | Create | `/setup` wizard command with multi-step View |
| `src/commands/setup.py` | Delete | Old role-only setup (replaced by config_cmd + setup_wizard) |
| `src/services/discord_service.py` | Modify | Swap old setup import for new config + setup_wizard imports |
| `src/commands/help_cmd.py` | Modify | Update HELP_TEXT: remove old setup entries, add config + setup |
| `tests/test_help_coverage.py` | Modify | Add new config/setup imports to `_build_tree()` |
| `tests/test_config_meta.py` | Create | Tests for settings registry validation |
| `tests/test_config_cmd.py` | Create | Tests for `/config` command handlers |
| `tests/test_setup_wizard.py` | Create | Tests for `/setup` wizard flow |

---

### Task 1: Settings Registry

**Files:**
- Create: `src/utils/config_meta.py`
- Create: `tests/test_config_meta.py`

- [ ] **Step 1: Write failing tests for the settings registry**

Create `tests/test_config_meta.py`:

```python
from __future__ import annotations

import pytest
from src.utils.config_meta import SETTINGS, validate_setting, SettingMeta


def test_all_settings_have_required_fields():
    for key, meta in SETTINGS.items():
        assert isinstance(meta, SettingMeta), f"{key} is not SettingMeta"
        assert meta.group in ("warnings", "schedule", "channels", "roles")
        assert meta.label
        assert meta.config_key
        assert meta.setting_type in ("integer", "time", "timezone", "channel")


def test_validate_integer_in_range():
    ok, val, err = validate_setting("warning_passive_days", "7")
    assert ok is True
    assert val == "7"
    assert err is None


def test_validate_integer_out_of_range():
    ok, val, err = validate_setting("warning_passive_days", "99")
    assert ok is False
    assert "1" in err and "30" in err


def test_validate_integer_not_a_number():
    ok, val, err = validate_setting("warning_passive_days", "abc")
    assert ok is False
    assert "integer" in err.lower()


def test_validate_time_valid():
    ok, val, err = validate_setting("daily_check_time", "09:00")
    assert ok is True


def test_validate_time_invalid():
    ok, val, err = validate_setting("daily_check_time", "25:99")
    assert ok is False


def test_validate_timezone_valid():
    ok, val, err = validate_setting("daily_check_timezone", "America/New_York")
    assert ok is True


def test_validate_timezone_invalid():
    ok, val, err = validate_setting("daily_check_timezone", "Mars/Olympus")
    assert ok is False


def test_validate_unknown_key():
    ok, val, err = validate_setting("nonexistent_key", "foo")
    assert ok is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config_meta.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.utils.config_meta'`

- [ ] **Step 3: Implement the settings registry**

Create `src/utils/config_meta.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple
from zoneinfo import available_timezones


@dataclass(frozen=True)
class SettingMeta:
    group: str
    label: str
    setting_type: str
    config_key: str
    sheets_type: str
    description: str
    min_val: Optional[int] = None
    max_val: Optional[int] = None


SETTINGS: dict[str, SettingMeta] = {
    "warning_passive_days": SettingMeta(
        group="warnings",
        label="Passive warning days",
        setting_type="integer",
        config_key="warning_passive_days",
        sheets_type="integer",
        description="Days before an unassigned date to post a passive warning",
        min_val=1,
        max_val=30,
    ),
    "warning_urgent_days": SettingMeta(
        group="warnings",
        label="Urgent warning days",
        setting_type="integer",
        config_key="warning_urgent_days",
        sheets_type="integer",
        description="Days before an unassigned date to post an urgent warning",
        min_val=1,
        max_val=14,
    ),
    "schedule_window_weeks": SettingMeta(
        group="schedule",
        label="Schedule window (weeks)",
        setting_type="integer",
        config_key="schedule_window_weeks",
        sheets_type="integer",
        description="Default number of weeks shown in /schedule",
        min_val=1,
        max_val=12,
    ),
    "daily_check_time": SettingMeta(
        group="schedule",
        label="Daily check time",
        setting_type="time",
        config_key="daily_check_time",
        sheets_type="string",
        description="Time of day for the automated warning check (HH:MM, 24-hour)",
    ),
    "daily_check_timezone": SettingMeta(
        group="schedule",
        label="Timezone",
        setting_type="timezone",
        config_key="daily_check_timezone",
        sheets_type="string",
        description="IANA timezone for the daily check (e.g. America/Los_Angeles)",
    ),
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
}

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_VALID_TIMEZONES = available_timezones()


def validate_setting(key: str, value: str) -> Tuple[bool, Optional[str], Optional[str]]:
    meta = SETTINGS.get(key)
    if meta is None:
        return False, None, f"Unknown setting: `{key}`"

    if meta.setting_type == "integer":
        try:
            n = int(value)
        except ValueError:
            return False, None, f"`{meta.label}` must be an integer."
        if meta.min_val is not None and n < meta.min_val:
            return False, None, f"`{meta.label}` must be between {meta.min_val} and {meta.max_val}."
        if meta.max_val is not None and n > meta.max_val:
            return False, None, f"`{meta.label}` must be between {meta.min_val} and {meta.max_val}."
        return True, str(n), None

    if meta.setting_type == "time":
        if not _TIME_RE.match(value):
            return False, None, f"`{meta.label}` must be in HH:MM 24-hour format (e.g. 09:00)."
        return True, value, None

    if meta.setting_type == "timezone":
        if value not in _VALID_TIMEZONES:
            return False, None, f"`{value}` is not a valid IANA timezone."
        return True, value, None

    if meta.setting_type == "channel":
        return True, value, None

    return False, None, f"Unknown type for `{key}`."
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config_meta.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/utils/config_meta.py tests/test_config_meta.py
git commit -m "feat: add settings registry with validation for /config command"
```

---

### Task 2: `/config` Command Group

**Files:**
- Create: `src/commands/config_cmd.py`
- Create: `tests/test_config_cmd.py`

- [ ] **Step 1: Write failing tests for `/config show`**

Create `tests/test_config_cmd.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.models import Configuration
from src.commands.config_cmd import build_group


@pytest.fixture
def sheets():
    return MagicMock()


@pytest.fixture
def cache():
    c = MagicMock()
    c.config = Configuration.default()
    c.refresh = AsyncMock()
    return c


@pytest.fixture
def group(sheets, cache):
    return build_group(sheets, cache)


def test_config_group_has_expected_subgroups(group):
    names = {cmd.name for cmd in group.commands}
    assert "show" in names
    assert "warnings" in names
    assert "schedule" in names
    assert "channels" in names
    assert "roles" in names


def test_config_group_name(group):
    assert group.name == "config"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config_cmd.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.commands.config_cmd'`

- [ ] **Step 3: Implement `/config` command group**

Create `src/commands/config_cmd.py`:

```python
from __future__ import annotations

import json

import discord
from discord import app_commands
from zoneinfo import available_timezones

from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService
from src.utils.auth import is_owner
from src.utils.config_meta import SETTINGS, validate_setting

BUCKETS = {
    "admin": "admin_role_ids",
    "host": "host_role_ids",
    "member": "member_role_ids",
}
BUCKET_CHOICES = [app_commands.Choice(name=n, value=n) for n in BUCKETS]

_TZ_CACHE: list[str] = sorted(available_timezones())


def build_group(sheets: SheetsService, cache: CacheService) -> app_commands.Group:
    group = app_commands.Group(name="config", description="View and change bot configuration")

    async def _guard(interaction: discord.Interaction) -> bool:
        if not is_owner(interaction.user, cache.config):
            await interaction.response.send_message("This command is owner-only.", ephemeral=True)
            return False
        return True

    # ── /config show ──

    @group.command(name="show", description="Display all current configuration")
    async def config_show(interaction: discord.Interaction) -> None:
        if not await _guard(interaction):
            return
        cfg = cache.config
        guild = interaction.guild

        def _channel_mention(cid: str | None) -> str:
            if cid:
                return f"<#{cid}>"
            return "*not set*"

        def _role_mentions(ids: list[int]) -> str:
            if not ids:
                return "*none*"
            if guild:
                names = []
                for rid in ids:
                    role = guild.get_role(rid)
                    names.append(role.mention if role else f"`{rid}`")
                return ", ".join(names)
            return ", ".join(f"`{r}`" for r in ids)

        lines = [
            "**Warnings**",
            f"  Passive warning days: **{cfg.warning_passive_days}**",
            f"  Urgent warning days: **{cfg.warning_urgent_days}**",
            "",
            "**Schedule**",
            f"  Window weeks: **{cfg.schedule_window_weeks}**",
            f"  Daily check time: **{cfg.daily_check_time}**",
            f"  Timezone: **{cfg.daily_check_timezone}**",
            "",
            "**Channels**",
            f"  Schedule channel: {_channel_mention(cfg.schedule_channel_id)}",
            f"  Warnings channel: {_channel_mention(cfg.warnings_channel_id)}",
            "",
            "**Roles**",
            f"  Admin: {_role_mentions(cfg.admin_role_ids)}",
            f"  Host: {_role_mentions(cfg.host_role_ids)}",
            f"  Member: {_role_mentions(cfg.member_role_ids)}",
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    # ── /config warnings ──

    warnings_group = app_commands.Group(
        name="warnings", description="Configure warning thresholds", parent=group
    )

    @warnings_group.command(name="passive_days", description="Set passive warning threshold (1-30)")
    @app_commands.describe(value="Days before event for passive warning")
    async def warnings_passive(interaction: discord.Interaction, value: int) -> None:
        if not await _guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        ok, val, err = validate_setting("warning_passive_days", str(value))
        if not ok:
            await interaction.followup.send(err, ephemeral=True)
            return
        old = cache.config.warning_passive_days
        sheets.update_configuration("warning_passive_days", val, type_="integer")
        await cache.refresh(force=True)
        await interaction.followup.send(
            f"Passive warning days: **{old}** -> **{val}**", ephemeral=True
        )

    @warnings_group.command(name="urgent_days", description="Set urgent warning threshold (1-14)")
    @app_commands.describe(value="Days before event for urgent warning")
    async def warnings_urgent(interaction: discord.Interaction, value: int) -> None:
        if not await _guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        ok, val, err = validate_setting("warning_urgent_days", str(value))
        if not ok:
            await interaction.followup.send(err, ephemeral=True)
            return
        old = cache.config.warning_urgent_days
        sheets.update_configuration("warning_urgent_days", val, type_="integer")
        await cache.refresh(force=True)
        await interaction.followup.send(
            f"Urgent warning days: **{old}** -> **{val}**", ephemeral=True
        )

    # ── /config schedule ──

    schedule_group = app_commands.Group(
        name="schedule", description="Configure schedule settings", parent=group
    )

    @schedule_group.command(name="window_weeks", description="Set default schedule window (1-12 weeks)")
    @app_commands.describe(value="Number of weeks to show in /schedule")
    async def schedule_window(interaction: discord.Interaction, value: int) -> None:
        if not await _guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        ok, val, err = validate_setting("schedule_window_weeks", str(value))
        if not ok:
            await interaction.followup.send(err, ephemeral=True)
            return
        old = cache.config.schedule_window_weeks
        sheets.update_configuration("schedule_window_weeks", val, type_="integer")
        await cache.refresh(force=True)
        await interaction.followup.send(
            f"Schedule window: **{old}** -> **{val}** weeks", ephemeral=True
        )

    @schedule_group.command(name="check_time", description="Set daily warning check time (HH:MM)")
    @app_commands.describe(value="Time in 24-hour format, e.g. 09:00")
    async def schedule_check_time(interaction: discord.Interaction, value: str) -> None:
        if not await _guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        ok, val, err = validate_setting("daily_check_time", value)
        if not ok:
            await interaction.followup.send(err, ephemeral=True)
            return
        old = cache.config.daily_check_time
        sheets.update_configuration("daily_check_time", val, type_="string")
        await cache.refresh(force=True)
        await interaction.followup.send(
            f"Daily check time: **{old}** -> **{val}**", ephemeral=True
        )

    @schedule_group.command(name="check_timezone", description="Set daily check timezone")
    @app_commands.describe(value="IANA timezone, e.g. America/New_York")
    async def schedule_check_timezone(interaction: discord.Interaction, value: str) -> None:
        if not await _guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        ok, val, err = validate_setting("daily_check_timezone", value)
        if not ok:
            await interaction.followup.send(err, ephemeral=True)
            return
        old = cache.config.daily_check_timezone
        sheets.update_configuration("daily_check_timezone", val, type_="string")
        await cache.refresh(force=True)
        await interaction.followup.send(
            f"Timezone: **{old}** -> **{val}**", ephemeral=True
        )

    @schedule_check_timezone.autocomplete("value")
    async def _tz_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        lower = current.lower()
        matches = [tz for tz in _TZ_CACHE if lower in tz.lower()]
        return [app_commands.Choice(name=tz, value=tz) for tz in matches[:25]]

    # ── /config channels ──

    channels_group = app_commands.Group(
        name="channels", description="Configure bot channels", parent=group
    )

    @channels_group.command(name="schedule_channel", description="Set the schedule posting channel")
    @app_commands.describe(channel="Channel for schedule posts")
    async def channels_schedule(
        interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        if not await _guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        old = cache.config.schedule_channel_id
        sheets.update_configuration("schedule_channel_id", str(channel.id), type_="string")
        await cache.refresh(force=True)
        old_mention = f"<#{old}>" if old else "*not set*"
        await interaction.followup.send(
            f"Schedule channel: {old_mention} -> {channel.mention}", ephemeral=True
        )

    @channels_group.command(name="warnings_channel", description="Set the warnings posting channel")
    @app_commands.describe(channel="Channel for warning posts")
    async def channels_warnings(
        interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        if not await _guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        old = cache.config.warnings_channel_id
        sheets.update_configuration("warnings_channel_id", str(channel.id), type_="string")
        await cache.refresh(force=True)
        old_mention = f"<#{old}>" if old else "*not set*"
        await interaction.followup.send(
            f"Warnings channel: {old_mention} -> {channel.mention}", ephemeral=True
        )

    # ── /config roles ──

    roles_group = app_commands.Group(
        name="roles", description="Configure role assignments", parent=group
    )

    def _current_role_ids(bucket: str) -> list[int]:
        return list(getattr(cache.config, BUCKETS[bucket]))

    async def _persist_roles(bucket: str, ids: list[int]) -> None:
        unique = sorted({int(x) for x in ids})
        sheets.update_configuration(BUCKETS[bucket], json.dumps(unique), type_="json")
        await cache.refresh(force=True)

    @roles_group.command(name="add", description="Add a Discord role to a bucket (admin/host/member)")
    @app_commands.choices(bucket=BUCKET_CHOICES)
    async def roles_add(
        interaction: discord.Interaction,
        bucket: app_commands.Choice[str],
        role: discord.Role,
    ) -> None:
        if not await _guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        ids = _current_role_ids(bucket.value)
        if role.id in ids:
            await interaction.followup.send(
                f"`{role.name}` is already in `{bucket.value}`.", ephemeral=True
            )
            return
        ids.append(role.id)
        await _persist_roles(bucket.value, ids)
        await interaction.followup.send(
            f"Added `{role.name}` to `{bucket.value}`.", ephemeral=True
        )

    @roles_group.command(name="remove", description="Remove a Discord role from a bucket")
    @app_commands.choices(bucket=BUCKET_CHOICES)
    async def roles_remove(
        interaction: discord.Interaction,
        bucket: app_commands.Choice[str],
        role: discord.Role,
    ) -> None:
        if not await _guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        ids = _current_role_ids(bucket.value)
        if role.id not in ids:
            await interaction.followup.send(
                f"`{role.name}` is not in `{bucket.value}`.", ephemeral=True
            )
            return
        ids = [x for x in ids if x != role.id]
        await _persist_roles(bucket.value, ids)
        await interaction.followup.send(
            f"Removed `{role.name}` from `{bucket.value}`.", ephemeral=True
        )

    @roles_group.command(name="clear", description="Clear all roles from a bucket")
    @app_commands.choices(bucket=BUCKET_CHOICES)
    async def roles_clear(
        interaction: discord.Interaction,
        bucket: app_commands.Choice[str],
    ) -> None:
        if not await _guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        await _persist_roles(bucket.value, [])
        await interaction.followup.send(
            f"Cleared all roles from `{bucket.value}`.", ephemeral=True
        )

    return group
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config_cmd.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/commands/config_cmd.py tests/test_config_cmd.py
git commit -m "feat: add /config command group with warnings, schedule, channels, roles subcommands"
```

---

### Task 3: `/setup` Wizard

**Files:**
- Create: `src/commands/setup_wizard.py`
- Create: `tests/test_setup_wizard.py`

- [ ] **Step 1: Write failing tests for the wizard**

Create `tests/test_setup_wizard.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock, AsyncMock

import pytest

from src.models.models import Configuration
from src.commands.setup_wizard import build_command


@pytest.fixture
def sheets():
    return MagicMock()


@pytest.fixture
def cache():
    c = MagicMock()
    c.config = Configuration.default()
    c.refresh = AsyncMock()
    return c


def test_setup_command_name(sheets, cache):
    cmd = build_command(sheets, cache)
    assert cmd.name == "setup"


def test_setup_command_description(sheets, cache):
    cmd = build_command(sheets, cache)
    assert "wizard" in cmd.description.lower() or "guided" in cmd.description.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_setup_wizard.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement the setup wizard**

Create `src/commands/setup_wizard.py`:

```python
from __future__ import annotations

import json
from typing import Optional

import discord
from discord import app_commands, ui

from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService
from src.utils.auth import is_owner
from src.utils.config_meta import SETTINGS, validate_setting


def _channel_mention(cid: Optional[str]) -> str:
    return f"<#{cid}>" if cid else "*not set*"


def _role_mentions(guild: Optional[discord.Guild], ids: list[int]) -> str:
    if not ids:
        return "*none*"
    if guild:
        names = []
        for rid in ids:
            role = guild.get_role(rid)
            names.append(role.mention if role else f"`{rid}`")
        return ", ".join(names)
    return ", ".join(f"`{r}`" for r in ids)


class SetupWizardView(ui.View):
    def __init__(
        self,
        sheets: SheetsService,
        cache: CacheService,
        interaction: discord.Interaction,
    ) -> None:
        super().__init__(timeout=1800)
        self.sheets = sheets
        self.cache = cache
        self.original_interaction = interaction
        self.step = 0

    def _build_roles_embed(self) -> discord.Embed:
        cfg = self.cache.config
        guild = self.original_interaction.guild
        embed = discord.Embed(
            title="Setup — Step 1/4: Roles",
            description="Let's set up who can do what.\n\nSelect roles for each bucket below, or skip to keep current values.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Admin", value=_role_mentions(guild, cfg.admin_role_ids), inline=True)
        embed.add_field(name="Host", value=_role_mentions(guild, cfg.host_role_ids), inline=True)
        embed.add_field(name="Member", value=_role_mentions(guild, cfg.member_role_ids), inline=True)
        return embed

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
        return embed

    def _build_summary_embed(self) -> discord.Embed:
        cfg = self.cache.config
        guild = self.original_interaction.guild
        embed = discord.Embed(
            title="Setup — Step 4/4: Summary",
            description="Here's your configuration.",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Roles",
            value=(
                f"Admin: {_role_mentions(guild, cfg.admin_role_ids)}\n"
                f"Host: {_role_mentions(guild, cfg.host_role_ids)}\n"
                f"Member: {_role_mentions(guild, cfg.member_role_ids)}"
            ),
            inline=False,
        )
        embed.add_field(
            name="Channels",
            value=(
                f"Schedule: {_channel_mention(cfg.schedule_channel_id)}\n"
                f"Warnings: {_channel_mention(cfg.warnings_channel_id)}"
            ),
            inline=False,
        )
        embed.add_field(
            name="Schedule",
            value=(
                f"Check time: {cfg.daily_check_time} ({cfg.daily_check_timezone})\n"
                f"Passive warning: {cfg.warning_passive_days} days\n"
                f"Urgent warning: {cfg.warning_urgent_days} days\n"
                f"Window: {cfg.schedule_window_weeks} weeks"
            ),
            inline=False,
        )
        return embed

    async def _show_step(self, interaction: discord.Interaction) -> None:
        self.clear_items()

        if self.step == 0:
            embed = self._build_roles_embed()
            for bucket_label, bucket_key in [("Admin", "admin"), ("Host", "host"), ("Member", "member")]:
                select = _RoleSelectForBucket(self, bucket_key, placeholder=f"Select {bucket_label} roles...")
                self.add_item(select)
            self.add_item(_NextButton(self, label="Next"))

        elif self.step == 1:
            embed = self._build_channels_embed()
            self.add_item(_ChannelSelectForSetting(self, "schedule_channel_id", placeholder="Select schedule channel..."))
            self.add_item(_ChannelSelectForSetting(self, "warnings_channel_id", placeholder="Select warnings channel..."))
            self.add_item(_NextButton(self, label="Next"))

        elif self.step == 2:
            embed = self._build_schedule_embed()
            self.add_item(_CustomizeButton(self))
            self.add_item(_NextButton(self, label="Use defaults & finish"))

        else:
            embed = self._build_summary_embed()
            self.add_item(_DoneButton(self))

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self) -> None:
        self.clear_items()
        embed = discord.Embed(title="Setup timed out", color=discord.Color.grayed_out())
        try:
            await self.original_interaction.edit_original_response(embed=embed, view=self)
        except discord.HTTPException:
            pass


class _NextButton(ui.Button):
    def __init__(self, wizard: SetupWizardView, label: str = "Next") -> None:
        super().__init__(style=discord.ButtonStyle.primary, label=label)
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction) -> None:
        self.wizard.step += 1
        await self.wizard._show_step(interaction)


class _DoneButton(ui.Button):
    def __init__(self, wizard: SetupWizardView) -> None:
        super().__init__(style=discord.ButtonStyle.success, label="Looks good!")
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction) -> None:
        self.wizard.clear_items()
        self.wizard.stop()
        embed = discord.Embed(
            title="Setup complete!",
            description="Use `/config show` to review settings or `/config <group>` to change individual values.",
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=embed, view=self.wizard)


class _RoleSelectForBucket(ui.RoleSelect):
    def __init__(self, wizard: SetupWizardView, bucket: str, **kwargs) -> None:
        super().__init__(min_values=0, max_values=10, **kwargs)
        self.wizard = wizard
        self.bucket = bucket
        self._config_key = {
            "admin": "admin_role_ids",
            "host": "host_role_ids",
            "member": "member_role_ids",
        }[bucket]

    async def callback(self, interaction: discord.Interaction) -> None:
        ids = [r.id for r in self.values]
        self.wizard.sheets.update_configuration(
            self._config_key, json.dumps(sorted(ids)), type_="json"
        )
        await self.wizard.cache.refresh(force=True)
        names = ", ".join(r.name for r in self.values) or "*cleared*"
        await interaction.response.send_message(
            f"Set **{self.bucket}** roles to: {names}", ephemeral=True
        )


class _ChannelSelectForSetting(ui.ChannelSelect):
    def __init__(self, wizard: SetupWizardView, config_key: str, **kwargs) -> None:
        super().__init__(
            min_values=0,
            max_values=1,
            channel_types=[discord.ChannelType.text],
            **kwargs,
        )
        self.wizard = wizard
        self._config_key = config_key

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.values:
            ch = self.values[0]
            self.wizard.sheets.update_configuration(
                self._config_key, str(ch.id), type_="string"
            )
            await self.wizard.cache.refresh(force=True)
            await interaction.response.send_message(
                f"Set to {ch.mention}", ephemeral=True
            )
        else:
            await interaction.response.send_message("No channel selected.", ephemeral=True)


class _ScheduleModal(ui.Modal, title="Customize Schedule Settings"):
    check_time = ui.TextInput(label="Daily check time (HH:MM)", placeholder="09:00", max_length=5)
    timezone = ui.TextInput(label="Timezone (IANA)", placeholder="America/Los_Angeles", max_length=50)
    passive_days = ui.TextInput(label="Passive warning days (1-30)", placeholder="7", max_length=2)
    urgent_days = ui.TextInput(label="Urgent warning days (1-14)", placeholder="3", max_length=2)
    window_weeks = ui.TextInput(label="Schedule window weeks (1-12)", placeholder="4", max_length=2)

    def __init__(self, wizard: SetupWizardView) -> None:
        super().__init__()
        self.wizard = wizard
        cfg = wizard.cache.config
        self.check_time.default = cfg.daily_check_time
        self.timezone.default = cfg.daily_check_timezone
        self.passive_days.default = str(cfg.warning_passive_days)
        self.urgent_days.default = str(cfg.warning_urgent_days)
        self.window_weeks.default = str(cfg.schedule_window_weeks)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        errors: list[str] = []
        updates: list[tuple[str, str, str]] = []

        for key, field_value in [
            ("daily_check_time", self.check_time.value),
            ("daily_check_timezone", self.timezone.value),
            ("warning_passive_days", self.passive_days.value),
            ("warning_urgent_days", self.urgent_days.value),
            ("schedule_window_weeks", self.window_weeks.value),
        ]:
            ok, val, err = validate_setting(key, field_value.strip())
            if ok:
                meta = SETTINGS[key]
                updates.append((key, val, meta.sheets_type))
            else:
                errors.append(err)

        if errors:
            await interaction.response.send_message(
                "**Validation errors:**\n" + "\n".join(f"- {e}" for e in errors),
                ephemeral=True,
            )
            return

        for key, val, type_ in updates:
            self.wizard.sheets.update_configuration(key, val, type_=type_)
        await self.wizard.cache.refresh(force=True)

        self.wizard.step = 3
        await self.wizard._show_step(interaction)


class _CustomizeButton(ui.Button):
    def __init__(self, wizard: SetupWizardView) -> None:
        super().__init__(style=discord.ButtonStyle.secondary, label="Customize")
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(_ScheduleModal(self.wizard))


def build_command(sheets: SheetsService, cache: CacheService) -> app_commands.Command:
    @app_commands.command(name="setup", description="Guided setup wizard for bot configuration")
    async def setup_cmd(interaction: discord.Interaction) -> None:
        if not is_owner(interaction.user, cache.config):
            await interaction.response.send_message("This command is owner-only.", ephemeral=True)
            return
        if interaction.guild is None:
            await interaction.response.send_message("Run this in a server.", ephemeral=True)
            return

        view = SetupWizardView(sheets, cache, interaction)
        embed = view._build_roles_embed()
        for bucket_label, bucket_key in [("Admin", "admin"), ("Host", "host"), ("Member", "member")]:
            select = _RoleSelectForBucket(view, bucket_key, placeholder=f"Select {bucket_label} roles...")
            view.add_item(select)
        view.add_item(_NextButton(view, label="Next"))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    return setup_cmd
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_setup_wizard.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/commands/setup_wizard.py tests/test_setup_wizard.py
git commit -m "feat: add /setup wizard with multi-step guided configuration"
```

---

### Task 4: Wire Up & Migrate

**Files:**
- Delete: `src/commands/setup.py`
- Modify: `src/services/discord_service.py:15-16,50`
- Modify: `src/commands/help_cmd.py:10-39`
- Modify: `tests/test_help_coverage.py:1-35`

- [ ] **Step 1: Update discord_service.py imports and registration**

In `src/services/discord_service.py`, replace the setup import and registration:

Change line 15:
```python
# old
from src.commands import setup as setup_mod
# new
from src.commands import config_cmd as config_mod
from src.commands import setup_wizard as setup_wizard_mod
```

Change line 50 in `_register_commands`:
```python
# old
self.tree.add_command(setup_mod.build_group(self.sheets, self.cache))
# new
self.tree.add_command(config_mod.build_group(self.sheets, self.cache))
self.tree.add_command(setup_wizard_mod.build_command(self.sheets, self.cache))
```

- [ ] **Step 2: Update help_cmd.py**

In `src/commands/help_cmd.py`, update `HELP_TEXT`:

Replace the `HELP_TEXT` dict with:
```python
HELP_TEXT = {
    None: (
        "**Commands**\n"
        "• `/schedule [weeks] [date]` — View upcoming host schedule\n"
        "• `/listdates [user]` — Upcoming dates for a user\n"
        "• `/warnings` — Check unassigned dates needing hosts\n"
        "• `/volunteer date date:[date] [user]` — Sign up for an open date\n"
        "• `/volunteer recurring pattern:[pattern] [user]` — Recurring pattern\n"
        "• `/unvolunteer date date:[date] [user]` — Cancel a date\n"
        "• `/unvolunteer recurring [user]` — Cancel recurring pattern\n"
        "• `/config show` — (owner) View all configuration\n"
        "• `/config <group> <setting>` — (owner) Change a setting\n"
        "• `/setup` — (owner) Guided setup wizard\n"
        "• `/sync` — (admin) Force sync with Google Sheets\n"
        "• `/reset` — (admin) Reset database cache\n"
        "• `/sheet` — Link to the backing Google Sheet\n"
        "• `/help [command]` — This help"
    ),
    "volunteer": "Use `/volunteer date` to claim an open date from the autocomplete dropdown, "
                 "or `/volunteer recurring pattern:'every 2nd Tuesday'` to set up a pattern.",
    "unvolunteer": "Use `/unvolunteer date` to cancel a specific hosting commitment, or "
                   "`/unvolunteer recurring` to cancel a recurring pattern (clears future dates).",
    "schedule": "Use `/schedule` to view the next N weeks (default 4, max 12). "
                "Pass `date:YYYY-MM-DD` to check a single date.",
    "warnings": "Use `/warnings` to see any unassigned dates within the warning window. "
                "Response is always private.",
    "listdates": "Use `/listdates` to view your upcoming dates, or `/listdates user:@x` "
                 "(hosts/admins only) to view another user.",
    "config": "Owner-only. Use `/config show` to see all settings, or `/config warnings`, "
              "`/config schedule`, `/config channels`, `/config roles` to change values.",
    "setup": "Owner-only. Guided wizard that walks through all essential bot configuration.",
    "sync": "Admin-only. Forces a full resync of local cache from Google Sheets.",
    "reset": "Admin-only. Displays the reset procedure and requires confirmation.",
    "sheet": "Shows the URL of the backing Google Sheet. You need to be "
             "granted view access to actually open it.",
}
```

- [ ] **Step 3: Update test_help_coverage.py**

In `tests/test_help_coverage.py`, replace the setup import and tree builder:

Replace lines 9-35 with:
```python
from src.commands import help_cmd as help_mod
from src.commands import listdates as listdates_mod
from src.commands import reset as reset_mod
from src.commands import schedule as schedule_mod
from src.commands import sheet as sheet_mod
from src.commands import config_cmd as config_mod
from src.commands import setup_wizard as setup_wizard_mod
from src.commands import sync as sync_mod
from src.commands import unvolunteer as unvolunteer_mod
from src.commands import volunteer as volunteer_mod
from src.commands import warnings_cmd as warnings_mod


def _build_tree() -> app_commands.CommandTree:
    sheets = MagicMock()
    cache = MagicMock()
    warnings = MagicMock()

    client = MagicMock()
    client._connection._command_tree = None
    tree = app_commands.CommandTree(client)
    tree.add_command(volunteer_mod.build_group(sheets, cache))
    tree.add_command(unvolunteer_mod.build_group(sheets, cache, warnings))
    tree.add_command(schedule_mod.build_command(cache))
    tree.add_command(listdates_mod.build_command(cache))
    tree.add_command(warnings_mod.build_command(cache, warnings))
    tree.add_command(sync_mod.build_command(sheets, cache))
    tree.add_command(reset_mod.build_command(sheets, cache))
    tree.add_command(config_mod.build_group(sheets, cache))
    tree.add_command(setup_wizard_mod.build_command(sheets, cache))
    tree.add_command(sheet_mod.build_command())
    tree.add_command(help_mod.build_command())
    return tree
```

- [ ] **Step 4: Delete old setup.py**

```bash
git rm src/commands/setup.py
```

- [ ] **Step 5: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All PASS — help coverage test passes with new config/setup entries, old setup references gone.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: replace /setup roles with /config group and /setup wizard"
```

---

### Task 5: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 2: Verify no references to old setup remain**

Run: `grep -r "setup_mod\|from src.commands import setup\b" src/ tests/ --include="*.py"`
Expected: No matches (only `setup_wizard` references).

- [ ] **Step 3: Verify imports work cleanly**

Run: `python -c "from src.commands.config_cmd import build_group; from src.commands.setup_wizard import build_command; print('OK')"`
Expected: `OK`
