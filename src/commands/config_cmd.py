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
