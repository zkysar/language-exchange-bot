from __future__ import annotations

from datetime import timedelta
from typing import Optional

import discord
from discord import app_commands

from src.services.cache_service import CacheService
from src.utils.auth import is_host, is_member
from src.utils.date_parser import format_display, parse_iso_date, today_la


def build_command(cache: CacheService) -> app_commands.Command:
    @app_commands.command(name="schedule", description="View upcoming host schedule")
    @app_commands.describe(
        weeks="Number of weeks to show (1-12, default 4)",
        date="Optional specific date (YYYY-MM-DD)",
    )
    async def schedule(
        interaction: discord.Interaction,
        weeks: Optional[int] = None,
        date: Optional[str] = None,
    ) -> None:
        if not is_member(interaction.user, cache.config):
            await interaction.response.send_message(
                "You do not have access to this bot.", ephemeral=True
            )
            return
        public = is_host(interaction.user, cache.config)
        await cache.refresh()

        if date:
            try:
                d = parse_iso_date(date)
            except ValueError:
                await interaction.response.send_message("Invalid date format.", ephemeral=True)
                return
            ev = cache.get_event(d)
            if ev and ev.is_assigned:
                content = f"**{format_display(d)}** → <@{ev.host_discord_id}>"
            else:
                content = f"**{format_display(d)}** → _unassigned_"
            await interaction.response.send_message(content, ephemeral=not public)
            return

        w = weeks if weeks else cache.config.schedule_window_weeks
        w = max(1, min(12, w))
        today = today_la()
        horizon = today + timedelta(weeks=w)
        lines = [f"**Schedule — next {w} week(s)**"]
        events = {e.date: e for e in cache.all_events()}
        for i in range((horizon - today).days + 1):
            d = today + timedelta(days=i)
            ev = events.get(d)
            if ev and ev.is_assigned:
                marker = "✅"
                who = f"<@{ev.host_discord_id}>"
                if ev.recurring_pattern_id:
                    who += " 🔁"
                lines.append(f"{marker} {format_display(d)} — {who}")
            else:
                # only show unassigned within window
                lines.append(f"❓ {format_display(d)} — _needs volunteer_")
        if len(lines) == 1:
            lines.append("_No dates in range._")
        # chunk if too long
        text = "\n".join(lines[:60])
        if len(lines) > 60:
            text += f"\n…({len(lines) - 60} more)"
        await interaction.response.send_message(text, ephemeral=not public)

    return schedule
