from __future__ import annotations

from datetime import timedelta
from typing import Optional

import discord
from discord import app_commands

from src.services.cache_service import CacheService
from src.utils.auth import is_host, is_member
from src.utils.date_parser import format_display, today_la


def build_command(cache: CacheService) -> app_commands.Command:
    @app_commands.command(name="listdates", description="List a user's upcoming hosting dates")
    @app_commands.describe(user="User (hosts/admins only for others; members see self)")
    async def listdates(
        interaction: discord.Interaction,
        user: Optional[discord.User] = None,
    ) -> None:
        if not is_member(interaction.user, cache.config):
            await interaction.response.send_message(
                "You do not have access to this bot.", ephemeral=True
            )
            return
        host_tier = is_host(interaction.user, cache.config)
        if user and not host_tier:
            await interaction.response.send_message(
                "Members may only view their own dates.", ephemeral=True
            )
            return
        target = user or interaction.user
        await cache.refresh()
        today = today_la()
        horizon = today + timedelta(weeks=12)
        matches = [
            e for e in cache.all_events()
            if e.is_assigned
            and str(e.host_discord_id) == str(target.id)
            and today <= e.date <= horizon
        ]
        matches.sort(key=lambda e: e.date)
        if not matches:
            await interaction.response.send_message(
                f"<@{target.id}> has no upcoming dates.", ephemeral=not host_tier
            )
            return
        lines = [f"**Upcoming dates for <@{target.id}>**"]
        for ev in matches:
            tag = " 🔁" if ev.recurring_pattern_id else ""
            lines.append(f"• {format_display(ev.date)}{tag}")
        await interaction.response.send_message("\n".join(lines), ephemeral=not host_tier)

    return listdates
