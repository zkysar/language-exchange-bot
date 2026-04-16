from __future__ import annotations

import json
from zoneinfo import available_timezones

import discord
from discord import app_commands

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

SETTING_CHOICES = [
    app_commands.Choice(name=meta.label, value=key)
    for key, meta in SETTINGS.items()
]


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
            "**Channel**",
            f"  Announcement channel: {_channel_mention(cfg.announcement_channel_id)}",
            "",
            "**Roles**",
            f"  Admin: {_role_mentions(cfg.admin_role_ids)}",
            f"  Host: {_role_mentions(cfg.host_role_ids)}",
            f"  Member: {_role_mentions(cfg.member_role_ids)}",
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    # ── /config set ──

    @group.command(name="set", description="Change a bot setting")
    @app_commands.describe(
        setting="The setting to change",
        value="New value (number, time, timezone, or #channel mention)",
    )
    @app_commands.choices(setting=SETTING_CHOICES)
    async def config_set(
        interaction: discord.Interaction,
        setting: app_commands.Choice[str],
        value: str,
    ) -> None:
        if not await _guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)

        key = setting.value
        meta = SETTINGS[key]

        if meta.setting_type == "channel":
            channel_id = _parse_channel(value, interaction)
            if channel_id is None:
                await interaction.followup.send(
                    "Please provide a valid #channel mention or channel ID.",
                    ephemeral=True,
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

        ok, val, err = validate_setting(key, value)
        if not ok:
            await interaction.followup.send(err, ephemeral=True)
            return

        old = getattr(cache.config, meta.config_key)
        sheets.update_configuration(meta.config_key, val, type_=meta.sheets_type)
        await cache.refresh(force=True)
        await interaction.followup.send(
            f"{meta.label}: **{old}** -> **{val}**", ephemeral=True
        )

    @config_set.autocomplete("value")
    async def _value_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        focused = interaction.namespace.setting
        if focused == "daily_check_timezone":
            lower = current.lower()
            matches = [tz for tz in _TZ_CACHE if lower in tz.lower()]
            return [app_commands.Choice(name=tz, value=tz) for tz in matches[:25]]
        return []

    # ── /config roles ──

    ACTION_CHOICES = [
        app_commands.Choice(name="add", value="add"),
        app_commands.Choice(name="remove", value="remove"),
        app_commands.Choice(name="clear", value="clear"),
    ]

    def _current_role_ids(bucket: str) -> list[int]:
        return list(getattr(cache.config, BUCKETS[bucket]))

    async def _persist_roles(bucket: str, ids: list[int]) -> None:
        unique = sorted({int(x) for x in ids})
        sheets.update_configuration(BUCKETS[bucket], json.dumps(unique), type_="json")
        await cache.refresh(force=True)

    @group.command(name="roles", description="Add, remove, or clear roles for a bucket")
    @app_commands.describe(
        action="add, remove, or clear",
        bucket="Role bucket (admin, host, or member)",
        role="The role to add or remove (not needed for clear)",
    )
    @app_commands.choices(action=ACTION_CHOICES, bucket=BUCKET_CHOICES)
    async def config_roles(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        bucket: app_commands.Choice[str],
        role: discord.Role | None = None,
    ) -> None:
        if not await _guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)

        act = action.value
        bkt = bucket.value

        if act == "clear":
            await _persist_roles(bkt, [])
            await interaction.followup.send(
                f"Cleared all roles from `{bkt}`.", ephemeral=True
            )
            return

        if role is None:
            await interaction.followup.send(
                f"You must provide a role to `{act}`.", ephemeral=True
            )
            return

        ids = _current_role_ids(bkt)

        if act == "add":
            if role.id in ids:
                await interaction.followup.send(
                    f"`{role.name}` is already in `{bkt}`.", ephemeral=True
                )
                return
            ids.append(role.id)
            await _persist_roles(bkt, ids)
            await interaction.followup.send(
                f"Added `{role.name}` to `{bkt}`.", ephemeral=True
            )
        elif act == "remove":
            if role.id not in ids:
                await interaction.followup.send(
                    f"`{role.name}` is not in `{bkt}`.", ephemeral=True
                )
                return
            ids = [x for x in ids if x != role.id]
            await _persist_roles(bkt, ids)
            await interaction.followup.send(
                f"Removed `{role.name}` from `{bkt}`.", ephemeral=True
            )

    return group


def _parse_channel(value: str, interaction: discord.Interaction) -> str | None:
    import re

    match = re.match(r"<#(\d+)>", value)
    if match:
        return match.group(1)
    if value.isdigit() and interaction.guild:
        ch = interaction.guild.get_channel(int(value))
        if ch:
            return str(ch.id)
    return None
