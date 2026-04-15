from __future__ import annotations

import discord
from discord import app_commands

from src.services.cache_service import CacheService
from src.services.warning_service import WarningService
from src.utils.auth import is_member
from src.utils.date_parser import format_display


def build_command(cache: CacheService, warnings: WarningService) -> app_commands.Command:
    @app_commands.command(name="warnings", description="Check dates needing hosts")
    async def warnings_cmd(interaction: discord.Interaction) -> None:
        if not is_member(interaction.user, cache.config):
            await interaction.response.send_message(
                "You do not have access to this bot.", ephemeral=True
            )
            return
        items = await warnings.check()
        if not items:
            await interaction.response.send_message(
                "✅ No warnings — all upcoming dates are covered.", ephemeral=True
            )
            return
        lines = ["**⚠️ Warnings**"]
        for w in items:
            icon = "🚨" if w.severity == "urgent" else "⚠️"
            lines.append(f"{icon} {format_display(w.event_date)} — {w.days_until} day(s) — {w.severity}")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    return warnings_cmd
