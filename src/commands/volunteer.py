from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

import discord
from discord import app_commands

from src.models.models import EventDate, RecurringPattern
from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService, make_audit
from src.utils.auth import is_host
from src.utils.date_parser import (
    format_date,
    format_display,
    parse_iso_date,
    today_la,
)
from src.utils.logger import get_logger
from src.utils.pattern_parser import generate_dates, parse_pattern

log = get_logger(__name__)


class VolunteerCog(discord.ext.commands.Cog if False else object):  # placeholder typing
    pass


def build_group(sheets: SheetsService, cache: CacheService) -> app_commands.Group:
    group = app_commands.Group(name="volunteer", description="Volunteer to host events")

    async def open_date_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        await cache.refresh()
        today = today_la()
        horizon = today + timedelta(weeks=12)
        events = {e.date: e for e in cache.all_events()}
        choices: List[app_commands.Choice[str]] = []
        for i in range((horizon - today).days + 1):
            d = today + timedelta(days=i)
            ev = events.get(d)
            if ev and ev.is_assigned:
                continue
            label = format_display(d)
            if current and current.lower() not in label.lower() and current not in format_date(d):
                continue
            choices.append(app_commands.Choice(name=label, value=format_date(d)))
            if len(choices) >= 25:
                break
        return choices

    @group.command(name="date", description="Volunteer a user for a specific open date")
    @app_commands.describe(user="User to volunteer (defaults to you)", date="Open date (choose from list)")
    @app_commands.autocomplete(date=open_date_autocomplete)
    async def volunteer_date(
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
            await interaction.response.send_message(
                f"Invalid date `{date}`. Pick one from the autocomplete list.",
                ephemeral=True,
            )
            return
        if d < today_la():
            await interaction.response.send_message(
                "Cannot volunteer for a past date.", ephemeral=True
            )
            return

        await interaction.response.defer()
        async with sheets.write_lock:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, cache.sheets.load_schedule)
            await cache.refresh(force=True)
            existing = cache.get_event(d)
            if existing and existing.is_assigned:
                await interaction.followup.send(
                    f"**{format_display(d)}** is already assigned to "
                    f"<@{existing.host_discord_id}>."
                )
                return
            now = datetime.now(timezone.utc)
            event = EventDate(
                date=d,
                host_discord_id=str(target.id),
                host_username=target.display_name,
                assigned_at=now,
                assigned_by=str(interaction.user.id),
            )
            try:
                await loop.run_in_executor(None, sheets.upsert_schedule_row, event)
                await loop.run_in_executor(
                    None,
                    sheets.append_audit,
                    make_audit(
                        "VOLUNTEER",
                        str(interaction.user.id),
                        target_user_discord_id=str(target.id),
                        event_date=d,
                    ),
                )
                cache.upsert_event(event)
            except Exception as e:
                log.exception("volunteer write failed")
                await interaction.followup.send(f"Failed to update schedule: {e}")
                return

        await interaction.followup.send(
            f"<@{target.id}> is now hosting on **{format_display(d)}**."
        )

    @group.command(name="recurring", description="Preview and commit a recurring hosting pattern")
    @app_commands.describe(
        pattern="e.g. 'every 2nd Tuesday', 'weekly friday', 'biweekly saturday', 'monthly'",
        user="User (defaults to you)",
    )
    async def volunteer_recurring(
        interaction: discord.Interaction,
        pattern: str,
        user: Optional[discord.User] = None,
    ) -> None:
        if not is_host(interaction.user, cache.config):
            await interaction.response.send_message(
                "This command requires the host role.", ephemeral=True
            )
            return
        target = user or interaction.user
        try:
            parsed = parse_pattern(pattern)
        except ValueError as e:
            await interaction.response.send_message(f"{e}", ephemeral=True)
            return

        start = today_la() + timedelta(days=1)
        dates = generate_dates(parsed, start, months=3)
        if not dates:
            await interaction.response.send_message(
                "No matching dates in the next 3 months.", ephemeral=True
            )
            return

        await cache.refresh()
        existing = {e.date: e for e in cache.all_events()}
        conflicts = [d for d in dates if d in existing and existing[d].is_assigned]
        available = [d for d in dates if d not in conflicts]

        preview_lines = [f"Pattern: `{pattern}` → {len(dates)} matches (next 3 months)"]
        preview_lines.append(f"**Will assign ({len(available)}):**")
        for d in available[:15]:
            preview_lines.append(f"- {format_display(d)}")
        if conflicts:
            preview_lines.append(f"**Conflicts ({len(conflicts)}):**")
            for d in conflicts[:10]:
                ev = existing[d]
                preview_lines.append(f"- {format_display(d)} → <@{ev.host_discord_id}>")

        view = _ConfirmView(sheets, cache, target, interaction.user, parsed, available)
        await interaction.response.send_message(
            "\n".join(preview_lines), view=view
        )

    return group


class _ConfirmView(discord.ui.View):
    def __init__(
        self,
        sheets: SheetsService,
        cache: CacheService,
        target: discord.abc.User,
        invoker: discord.abc.User,
        parsed,
        dates: List[date],
    ) -> None:
        super().__init__(timeout=120)
        self.sheets = sheets
        self.cache = cache
        self.target = target
        self.invoker = invoker
        self.parsed = parsed
        self.dates = dates

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message("Only the invoker can confirm.", ephemeral=True)
            return
        await interaction.response.defer()
        async with self.sheets.write_lock:
            loop = asyncio.get_running_loop()
            pattern_id = str(uuid.uuid4())
            pattern = RecurringPattern(
                pattern_id=pattern_id,
                host_discord_id=str(self.target.id),
                host_username=self.target.display_name,
                pattern_description=self.parsed.description,
                pattern_rule=json.dumps({
                    "kind": self.parsed.kind,
                    "weekday": self.parsed.weekday,
                    "nth": self.parsed.nth,
                    "day_of_month": self.parsed.day_of_month,
                }),
                start_date=self.dates[0] if self.dates else today_la(),
                created_at=datetime.now(timezone.utc),
                is_active=True,
            )
            try:
                await loop.run_in_executor(None, self.sheets.append_pattern, pattern)
                now = datetime.now(timezone.utc)
                assigned = 0
                for d in self.dates:
                    current = self.cache.get_event(d)
                    if current and current.is_assigned:
                        continue
                    event = EventDate(
                        date=d,
                        host_discord_id=str(self.target.id),
                        host_username=self.target.display_name,
                        recurring_pattern_id=pattern_id,
                        assigned_at=now,
                        assigned_by=str(self.invoker.id),
                    )
                    await loop.run_in_executor(None, self.sheets.upsert_schedule_row, event)
                    self.cache.upsert_event(event)
                    assigned += 1
                await loop.run_in_executor(
                    None,
                    self.sheets.append_audit,
                    make_audit(
                        "VOLUNTEER_RECURRING",
                        str(self.invoker.id),
                        target_user_discord_id=str(self.target.id),
                        recurring_pattern_id=pattern_id,
                        metadata={"count": assigned},
                    ),
                )
                self.cache.add_pattern(pattern)
            except Exception as e:
                log.exception("recurring commit failed")
                await interaction.followup.send(f"Failed: {e}")
                return
        self.stop()
        await interaction.followup.send(
            f"Created recurring pattern for <@{self.target.id}>: {assigned} dates assigned."
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message("Only the invoker can cancel.", ephemeral=True)
            return
        self.stop()
        await interaction.response.send_message("Cancelled.", ephemeral=True)
