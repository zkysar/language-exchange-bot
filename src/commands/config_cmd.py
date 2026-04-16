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

ACTION_CHOICES = [
    app_commands.Choice(name="get", value="get"),
    app_commands.Choice(name="set", value="set"),
    app_commands.Choice(name="add", value="add"),
    app_commands.Choice(name="remove", value="remove"),
]

KEY_CHOICES = [
    app_commands.Choice(name=meta.label, value=key)
    for key, meta in SETTINGS.items()
] + [
    app_commands.Choice(name=_ROLE_LABELS[bucket], value=bucket)
    for bucket in ROLE_BUCKETS
]


def build_command(sheets: SheetsService, cache: CacheService) -> app_commands.Command:
    @app_commands.command(name="config", description="View and change bot configuration")
    @app_commands.describe(
        action="What to do (default: get)",
        key="Which setting or role bucket",
        value="New value, channel mention, or role mention",
    )
    @app_commands.choices(action=ACTION_CHOICES, key=KEY_CHOICES)
    async def config(
        interaction: discord.Interaction,
        action: app_commands.Choice[str] | None = None,
        key: app_commands.Choice[str] | None = None,
        value: str | None = None,
    ) -> None:
        if not is_owner(interaction.user, cache.config):
            await interaction.response.send_message("This command is owner-only.", ephemeral=True)
            return

        act = action.value if action else "get"
        key_val = key.value if key else None

        if act == "get":
            await _handle_get(interaction, cache, key_val)
            return

        await interaction.response.defer(ephemeral=True)

        if act == "set":
            await _handle_set(interaction, sheets, cache, key_val, value)
        elif act in ("add", "remove"):
            await _handle_role_mutation(interaction, sheets, cache, act, key_val, value)

    @config.autocomplete("value")
    async def _value_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if getattr(interaction.namespace, "key", None) == "daily_check_timezone":
            lower = current.lower()
            matches = [tz for tz in _TZ_CACHE if lower in tz.lower()]
            return [app_commands.Choice(name=tz, value=tz) for tz in matches[:25]]
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
            "**Channel**",
            f"  Announcement channel: {_channel_mention(cfg.announcement_channel_id)}",
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
