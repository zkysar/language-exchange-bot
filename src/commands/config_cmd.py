from __future__ import annotations

import json
import re
from zoneinfo import available_timezones

import discord
from discord import app_commands

from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService
from src.utils.auth import is_owner
from src.utils.config_meta import SETTINGS, validate_setting

_TZ_CACHE: list[str] = sorted(available_timezones())

ROLE_BUCKETS: dict[str, str] = {
    "admin": "admin_role_ids",
    "host": "host_role_ids",
}
_ROLE_LABELS = {"admin": "Admin roles", "host": "Host roles"}

_SCALAR_ACTIONS = [
    app_commands.Choice(name="get", value="get"),
    app_commands.Choice(name="set", value="set"),
]
_LIST_ACTIONS = [
    app_commands.Choice(name="get", value="get"),
    app_commands.Choice(name="add", value="add"),
    app_commands.Choice(name="remove", value="remove"),
]
_ALL_ACTIONS = [
    app_commands.Choice(name="get", value="get"),
    app_commands.Choice(name="set", value="set"),
    app_commands.Choice(name="add", value="add"),
    app_commands.Choice(name="remove", value="remove"),
]

# Dropdown labels with format hints. Falls through to `meta.label` when not listed.
# Error messages and /config display still use the plain `meta.label`.
_KEY_DROPDOWN_LABELS: dict[str, str] = {
    "meeting_schedule": 'Meeting schedule — e.g. "every wednesday"',
}

_MEETING_SCHEDULE_SUGGESTIONS: list[str] = [
    "every monday",
    "every tuesday",
    "every wednesday",
    "every thursday",
    "every friday",
    "every saturday",
    "every sunday",
    "every 1st monday",
    "every 2nd tuesday",
    "every 2nd wednesday",
    "every 3rd thursday",
    "every last friday",
    "biweekly wednesday",
    "biweekly friday",
]

KEY_CHOICES = [
    app_commands.Choice(
        name=_KEY_DROPDOWN_LABELS.get(key, meta.label), value=key
    )
    for key, meta in SETTINGS.items()
] + [
    app_commands.Choice(name=_ROLE_LABELS[bucket], value=bucket)
    for bucket in ROLE_BUCKETS
]


def build_command(sheets: SheetsService, cache: CacheService) -> app_commands.Command:
    @app_commands.command(name="config", description="🤫 View and change bot configuration")
    @app_commands.describe(
        key="Which setting or role bucket",
        action="What to do (default: get)",
        value="New value, channel mention, or role mention",
    )
    @app_commands.choices(key=KEY_CHOICES)
    async def config(
        interaction: discord.Interaction,
        key: app_commands.Choice[str] | None = None,
        action: str | None = None,
        value: str | None = None,
    ) -> None:
        if not is_owner(interaction.user, cache.config):
            await interaction.response.send_message("This command is owner-only.", ephemeral=True)
            return

        key_val = key.value if key else None
        act = action if action else "get"

        if act == "get":
            await _handle_get(interaction, cache, key_val)
            return

        await interaction.response.defer(ephemeral=True)

        if act == "set":
            await _handle_set(interaction, sheets, cache, key_val, value)
        elif act in ("add", "remove"):
            await _handle_role_mutation(interaction, sheets, cache, act, key_val, value)

    @config.autocomplete("action")
    async def _action_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        selected_key = getattr(interaction.namespace, "key", None)
        if selected_key in ROLE_BUCKETS:
            choices = _LIST_ACTIONS
        elif selected_key in SETTINGS:
            choices = _SCALAR_ACTIONS
        else:
            choices = _ALL_ACTIONS
        lower = current.lower()
        return [c for c in choices if lower in c.name]

    @config.autocomplete("value")
    async def _value_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        key = getattr(interaction.namespace, "key", None)
        lower = current.lower()
        if key == "daily_check_timezone":
            matches = [tz for tz in _TZ_CACHE if lower in tz.lower()]
            return [app_commands.Choice(name=tz, value=tz) for tz in matches[:25]]
        if key == "meeting_schedule":
            matches = [
                s for s in _MEETING_SCHEDULE_SUGGESTIONS if lower in s.lower()
            ]
            return [app_commands.Choice(name=s, value=s) for s in matches[:25]]
        return []

    return config


# ── handlers ──────────────────────────────────────────────────────────────────

async def _handle_get(
    interaction: discord.Interaction,
    cache: CacheService,
    key_val: str | None,
) -> None:
    cfg = cache.config
    guild = interaction.guild

    def _channel_mention(cid: str | None) -> str:
        return f"<#{cid}>" if cid else "*not set*"

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

    if key_val is None:
        meeting_display = (
            f"**{cfg.meeting_schedule}**" if cfg.meeting_schedule else "*not set*"
        )

        def _nullable_int(n: int | None) -> str:
            return f"**{n}**" if n is not None else "*off*"

        lines = [
            "**Configuration**",
            "",
            "**Announcements**",
            f"  Schedule post interval (days): {_nullable_int(cfg.schedule_announcement_interval_days)}",
            f"  Schedule post lookahead (weeks): {_nullable_int(cfg.schedule_announcement_lookahead_weeks)}",
            f"  Passive warning days: {_nullable_int(cfg.warning_passive_days)}",
            f"  Urgent warning days: {_nullable_int(cfg.warning_urgent_days)}",
            f"  Announcement channel: {_channel_mention(cfg.announcement_channel_id)}",
            "",
            "**Schedule**",
            f"  Window weeks: **{cfg.schedule_window_weeks}**",
            f"  Daily check time: **{cfg.daily_check_time}**",
            f"  Timezone: **{cfg.daily_check_timezone}**",
            f"  Meeting schedule: {meeting_display}",
            "",
            "**Roles**",
            f"  Admin: {_role_mentions(cfg.admin_role_ids)}",
            f"  Host: {_role_mentions(cfg.host_role_ids)}",
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)
        return

    if key_val in ROLE_BUCKETS:
        ids = list(getattr(cfg, ROLE_BUCKETS[key_val]))
        label = _ROLE_LABELS[key_val]
        await interaction.response.send_message(
            f"**{label}:** {_role_mentions(ids)}", ephemeral=True
        )
        return

    if key_val in SETTINGS:
        meta = SETTINGS[key_val]
        raw = getattr(cfg, meta.config_key)
        if meta.setting_type == "channel":
            display = _channel_mention(raw)
        elif raw is None or raw == "":
            display = "*not set*"
        else:
            display = f"**{raw}**"
        await interaction.response.send_message(f"{meta.label}: {display}", ephemeral=True)
        return

    await interaction.response.send_message(f"Unknown key: `{key_val}`", ephemeral=True)


async def _handle_set(
    interaction: discord.Interaction,
    sheets: SheetsService,
    cache: CacheService,
    key_val: str | None,
    value: str | None,
) -> None:
    if key_val in ROLE_BUCKETS:
        await interaction.followup.send(
            "Use `add` or `remove` to manage role buckets.", ephemeral=True
        )
        return

    if key_val not in SETTINGS:
        await interaction.followup.send(f"Unknown key: `{key_val}`", ephemeral=True)
        return

    if value is None:
        await interaction.followup.send("Provide a value.", ephemeral=True)
        return

    meta = SETTINGS[key_val]

    if meta.setting_type == "channel":
        channel_id = _parse_channel(value, interaction)
        if channel_id is None:
            await interaction.followup.send(
                "Please provide a valid #channel mention or channel ID.", ephemeral=True
            )
            return
        old = getattr(cache.config, meta.config_key)
        sheets.update_configuration(meta.config_key, channel_id, type_=meta.sheets_type)
        await cache.refresh(force=True)
        old_mention = f"<#{old}>" if old else "*not set*"
        await interaction.followup.send(
            f"{meta.label}: {old_mention} -> <#{channel_id}>", ephemeral=True
        )
        return

    ok, val, err = validate_setting(key_val, value)
    if not ok:
        await interaction.followup.send(err, ephemeral=True)
        return

    old = getattr(cache.config, meta.config_key)
    sheets.update_configuration(meta.config_key, val, type_=meta.sheets_type)
    await cache.refresh(force=True)
    await interaction.followup.send(
        f"{meta.label}: **{old}** -> **{val}**", ephemeral=True
    )


async def _handle_role_mutation(
    interaction: discord.Interaction,
    sheets: SheetsService,
    cache: CacheService,
    act: str,
    key_val: str | None,
    value: str | None,
) -> None:
    if key_val not in ROLE_BUCKETS:
        await interaction.followup.send(
            "Use `set` for scalar settings.", ephemeral=True
        )
        return

    if value is None:
        await interaction.followup.send("Provide a role mention or ID.", ephemeral=True)
        return

    role_id = _parse_role(value)
    if role_id is None:
        await interaction.followup.send(
            "Provide a valid role mention (`<@&id>`) or role ID.", ephemeral=True
        )
        return

    bucket_key = ROLE_BUCKETS[key_val]
    ids = list(getattr(cache.config, bucket_key))

    if act == "add":
        if role_id in ids:
            await interaction.followup.send(
                f"`{role_id}` is already in `{key_val}`.", ephemeral=True
            )
            return
        ids.append(role_id)
        unique = sorted({int(x) for x in ids})
        sheets.update_configuration(bucket_key, json.dumps(unique), type_="json")
        await cache.refresh(force=True)
        await interaction.followup.send(
            f"Added `{role_id}` to `{key_val}`.", ephemeral=True
        )

    elif act == "remove":
        if role_id not in ids:
            await interaction.followup.send(
                f"`{role_id}` is not in `{key_val}`.", ephemeral=True
            )
            return
        ids = [x for x in ids if x != role_id]
        unique = sorted({int(x) for x in ids})
        sheets.update_configuration(bucket_key, json.dumps(unique), type_="json")
        await cache.refresh(force=True)
        await interaction.followup.send(
            f"Removed `{role_id}` from `{key_val}`.", ephemeral=True
        )


# ── helpers ───────────────────────────────────────────────────────────────────

def _parse_channel(value: str, interaction: discord.Interaction) -> str | None:
    match = re.match(r"<#(\d+)>", value)
    if match:
        return match.group(1)
    if value.isdigit() and interaction.guild:
        ch = interaction.guild.get_channel(int(value))
        if ch:
            return str(ch.id)
    return None


def _parse_role(value: str) -> int | None:
    match = re.match(r"<@&(\d+)>", value)
    if match:
        return int(match.group(1))
    if value.isdigit():
        return int(value)
    return None
