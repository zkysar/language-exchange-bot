from __future__ import annotations

from datetime import timedelta
from typing import Optional

import discord
from discord import app_commands

from src.services.cache_service import CacheService
from src.utils.auth import is_host
from src.utils.date_parser import format_display, parse_iso_date, today_la
from src.utils.meeting_schedule import generate_meeting_dates


def _host_display(ev) -> str:
    if ev.host_discord_id:
        return f"<@{ev.host_discord_id}>"
    return f"{ev.host_username} (not on Discord)"


def build_command(cache: CacheService) -> app_commands.Command:
    @app_commands.command(name="schedule", description="View upcoming host schedule")
    @app_commands.describe(
        weeks="Number of weeks to show (1-12, default 4)",
        date="Optional specific date (YYYY-MM-DD)",
        user="Filter to a specific user's dates",
    )
    async def schedule(
        interaction: discord.Interaction,
        weeks: Optional[int] = None,
        date: Optional[str] = None,
        user: Optional[discord.User] = None,
    ) -> None:
        host_tier = is_host(interaction.user, cache.config)

        if user and user != interaction.user and not host_tier:
            await interaction.response.send_message(
                "Members may only view their own dates.", ephemeral=True
            )
            return

        public = host_tier
        await cache.refresh()
        target_id = str(user.id) if user else None

        if date:
            try:
                d = parse_iso_date(date)
            except ValueError:
                await interaction.response.send_message("Invalid date format.", ephemeral=True)
                return
            ev = cache.get_event(d)
            if ev and ev.is_assigned:
                content = f"**{format_display(d)}** → {_host_display(ev)}"
            else:
                content = f"**{format_display(d)}** → _unassigned_"
            await interaction.response.send_message(content, ephemeral=not public)
            return

        w = weeks if weeks else cache.config.schedule_window_weeks
        w = max(1, min(12, w))
        today = today_la()
        horizon = today + timedelta(weeks=w)

        if target_id:
            matches = [
                e for e in cache.all_events()
                if e.is_assigned
                and str(e.host_discord_id) == target_id
                and today <= e.date <= horizon
            ]
            matches.sort(key=lambda e: e.date)
            if not matches:
                await interaction.response.send_message(
                    f"<@{target_id}> has no upcoming dates in the next {w} week(s).",
                    ephemeral=not public,
                )
                return
            lines = [f"**Upcoming dates for <@{target_id}> — next {w} week(s)**"]
            for ev in matches:
                tag = " 🔁" if ev.recurring_pattern_id else ""
                lines.append(f"• {format_display(ev.date)}{tag}")
        else:
            lines = [f"**Schedule — next {w} week(s)**"]
            events = {e.date: e for e in cache.all_events()}
            meeting_dates = generate_meeting_dates(cache.config, today, horizon)
            for i in range((horizon - today).days + 1):
                d = today + timedelta(days=i)
                if meeting_dates is not None and d not in meeting_dates:
                    continue
                ev = events.get(d)
                if ev and ev.is_assigned:
                    marker = "✅"
                    who = _host_display(ev)
                    if ev.recurring_pattern_id:
                        who += " 🔁"
                    lines.append(f"{marker} {format_display(d)} — {who}")
                else:
                    lines.append(f"❓ {format_display(d)} — _needs volunteer_")

        if len(lines) == 1:
            lines.append("_No dates in range._")
        text = "\n".join(lines[:60])
        if len(lines) > 60:
            text += f"\n…({len(lines) - 60} more)"
        await interaction.response.send_message(text, ephemeral=not public)

    return schedule
