from __future__ import annotations

import json

import discord
from discord import app_commands

from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService
from src.utils.auth import is_owner

BUCKETS = {
    "admin": "admin_role_ids",
    "host": "host_role_ids",
    "member": "member_role_ids",
}
BUCKET_CHOICES = [
    app_commands.Choice(name=name, value=name) for name in BUCKETS
]


def build_group(sheets: SheetsService, cache: CacheService) -> app_commands.Group:
    group = app_commands.Group(name="setup", description="Owner-only setup commands")

    async def _guard(interaction: discord.Interaction) -> bool:
        if not is_owner(interaction.user, cache.config):
            await interaction.response.send_message(
                "This command is owner-only.", ephemeral=True
            )
            return False
        return True

    def _current(bucket: str) -> list[int]:
        return list(getattr(cache.config, BUCKETS[bucket]))

    async def _persist(bucket: str, ids: list[int]) -> None:
        unique = sorted({int(x) for x in ids})
        sheets.update_configuration(BUCKETS[bucket], json.dumps(unique), type_="json")
        await cache.refresh(force=True)

    @group.command(name="roles", description="List server roles and show host/admin/member config")
    async def roles(interaction: discord.Interaction) -> None:
        if not is_owner(interaction.user, cache.config):
            await interaction.response.send_message(
                "This command is owner-only.", ephemeral=True
            )
            return
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "Run this in a guild.", ephemeral=True
            )
            return

        config = cache.config
        admin_ids = {int(x) for x in config.admin_role_ids}
        host_ids = {int(x) for x in config.host_role_ids}
        member_ids = {int(x) for x in config.member_role_ids}

        lines = [f"**Roles in {guild.name}**"]
        for role in sorted(guild.roles, key=lambda r: r.position, reverse=True):
            if role.is_default():
                continue
            tags = []
            if role.id in admin_ids:
                tags.append("admin")
            if role.id in host_ids:
                tags.append("host")
            if role.id in member_ids:
                tags.append("member")
            tag_str = f" — **{', '.join(tags)}**" if tags else ""
            lines.append(f"`{role.id}` · {role.name}{tag_str}")

        lines.append("")
        lines.append("**Configured**")
        lines.append(f"admin_role_ids: `{config.admin_role_ids}`")
        lines.append(f"host_role_ids: `{config.host_role_ids}`")
        lines.append(f"member_role_ids: `{config.member_role_ids}`")
        lines.append(f"owner_user_ids: `{config.owner_user_ids}`")

        content = "\n".join(lines)
        if len(content) > 1900:
            content = content[:1900] + "\n…(truncated)"
        await interaction.response.send_message(content, ephemeral=True)

    @group.command(name="role-add", description="Add a Discord role to a bucket (admin/host/member)")
    @app_commands.choices(bucket=BUCKET_CHOICES)
    async def role_add(
        interaction: discord.Interaction,
        bucket: app_commands.Choice[str],
        role: discord.Role,
    ) -> None:
        if not await _guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        ids = _current(bucket.value)
        if role.id in ids:
            await interaction.followup.send(
                f"`{role.name}` is already in `{BUCKETS[bucket.value]}`.", ephemeral=True
            )
            return
        ids.append(role.id)
        await _persist(bucket.value, ids)
        await interaction.followup.send(
            f"Added `{role.name}` ({role.id}) to `{BUCKETS[bucket.value]}`. Current: `{sorted(set(ids))}`",
            ephemeral=True,
        )

    @group.command(name="role-remove", description="Remove a Discord role from a bucket")
    @app_commands.choices(bucket=BUCKET_CHOICES)
    async def role_remove(
        interaction: discord.Interaction,
        bucket: app_commands.Choice[str],
        role: discord.Role,
    ) -> None:
        if not await _guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        ids = _current(bucket.value)
        if role.id not in ids:
            await interaction.followup.send(
                f"`{role.name}` is not in `{BUCKETS[bucket.value]}`.", ephemeral=True
            )
            return
        ids = [x for x in ids if x != role.id]
        await _persist(bucket.value, ids)
        await interaction.followup.send(
            f"Removed `{role.name}` from `{BUCKETS[bucket.value]}`. Current: `{sorted(set(ids))}`",
            ephemeral=True,
        )

    @group.command(name="role-clear", description="Clear all roles from a bucket")
    @app_commands.choices(bucket=BUCKET_CHOICES)
    async def role_clear(
        interaction: discord.Interaction,
        bucket: app_commands.Choice[str],
    ) -> None:
        if not await _guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        await _persist(bucket.value, [])
        await interaction.followup.send(
            f"Cleared `{BUCKETS[bucket.value]}`.", ephemeral=True
        )

    return group
