from __future__ import annotations

import asyncio
from typing import List, Optional

import discord
from discord import app_commands

from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService, make_audit
from src.services.warning_service import WarningService
from src.utils.auth import is_host
from src.utils.date_parser import (
    format_date,
    format_display,
    parse_iso_date,
    today_la,
)
from src.utils.logger import get_logger

log = get_logger(__name__)


def build_group(
    sheets: SheetsService,
    cache: CacheService,
    warnings: WarningService,
) -> app_commands.Group:
    group = app_commands.Group(name="unvolunteer", description="Cancel a hosting commitment")

    async def user_dates_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        await cache.refresh()
        today = today_la()
        # find user parameter from interaction namespace if provided
        target_id = None
        for opt in interaction.data.get("options", []) or []:
            for sub in opt.get("options", []) or []:
                if sub.get("name") == "user":
                    target_id = sub.get("value")
        if not target_id:
            target_id = str(interaction.user.id)
        choices: List[app_commands.Choice[str]] = []
        for ev in sorted(cache.all_events(), key=lambda e: e.date):
            if not ev.is_assigned or ev.date < today:
                continue
            if str(ev.host_discord_id) != str(target_id):
                continue
            label = format_display(ev.date)
            if current and current.lower() not in label.lower() and current not in format_date(ev.date):
                continue
            choices.append(app_commands.Choice(name=label, value=format_date(ev.date)))
            if len(choices) >= 25:
                break
        return choices

    @group.command(name="date", description="Remove a user from a hosting date")
    @app_commands.describe(date="Date to unvolunteer from", user="User (defaults to you)")
    @app_commands.autocomplete(date=user_dates_autocomplete)
    async def unvolunteer_date(
        interaction: discord.Interaction,
        date: str,
        user: Optional[discord.User] = None,
    ) -> None:
        if not is_host(interaction.user, cache.config):
            await interaction.response.send_message(
                "This command requires the host role.", ephemeral=True
            )
            return
        target = user or interaction.user
        try:
            d = parse_iso_date(date)
        except ValueError:
            await interaction.response.send_message("Invalid date.", ephemeral=True)
            return

        await interaction.response.defer()
        async with sheets.write_lock:
            loop = asyncio.get_running_loop()
            await cache.refresh(force=True)
            ev = cache.get_event(d)
            if not ev or not ev.is_assigned:
                await interaction.followup.send(f"No one is scheduled on **{format_display(d)}**.")
                return
            if str(ev.host_discord_id) != str(target.id):
                await interaction.followup.send(
                    f"<@{target.id}> is not assigned on **{format_display(d)}** "
                    f"(assigned: <@{ev.host_discord_id}>)."
                )
                return
            try:
                await loop.run_in_executor(None, sheets.clear_schedule_assignment, d)
                await loop.run_in_executor(
                    None,
                    sheets.append_audit,
                    make_audit(
                        "UNVOLUNTEER",
                        str(interaction.user.id),
                        target_user_discord_id=str(target.id),
                        event_date=d,
                    ),
                )
                cache.remove_event_assignment(d)
            except Exception as e:
                log.exception("unvolunteer failed")
                await interaction.followup.send(f"Failed: {e}")
                return

        msg = f"Removed <@{target.id}> from **{format_display(d)}**."
        # trigger immediate warning check
        try:
            items = await warnings.check()
            urgent = [w for w in items if w.event_date == d and w.severity == "urgent"]
            if urgent:
                msg += "\n⚠️ This date is within the urgent warning window."
        except Exception:
            log.exception("warning check failed")
        await interaction.followup.send(msg)

    @group.command(name="recurring", description="Cancel a recurring pattern and clear future dates")
    @app_commands.describe(user="User (defaults to you)")
    async def unvolunteer_recurring(
        interaction: discord.Interaction,
        user: Optional[discord.User] = None,
    ) -> None:
        if not is_host(interaction.user, cache.config):
            await interaction.response.send_message(
                "This command requires the host role.", ephemeral=True
            )
            return
        target = user or interaction.user
        await cache.refresh()
        patterns = cache.active_patterns_for(str(target.id))
        if not patterns:
            await interaction.response.send_message(
                f"<@{target.id}> has no active recurring patterns.", ephemeral=True
            )
            return

        await interaction.response.defer()
        async with sheets.write_lock:
            loop = asyncio.get_running_loop()
            today = today_la()
            total_cleared = 0
            for p in patterns:
                await loop.run_in_executor(None, sheets.deactivate_pattern, p.pattern_id)
                cleared = await loop.run_in_executor(
                    None, sheets.delete_future_pattern_rows, p.pattern_id, today
                )
                total_cleared += cleared
                cache.deactivate_pattern(p.pattern_id)
                await loop.run_in_executor(
                    None,
                    sheets.append_audit,
                    make_audit(
                        "UNVOLUNTEER_RECURRING",
                        str(interaction.user.id),
                        target_user_discord_id=str(target.id),
                        recurring_pattern_id=p.pattern_id,
                        metadata={"cleared": cleared},
                    ),
                )
            cache.invalidate()
            await cache.refresh(force=True)

        await interaction.followup.send(
            f"Deactivated {len(patterns)} pattern(s) for <@{target.id}>, "
            f"cleared {total_cleared} future date(s)."
        )

    return group
