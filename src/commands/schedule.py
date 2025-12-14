"""Schedule command handler."""

import logging
from datetime import timedelta
from typing import Any, Mapping, Optional

import discord
from discord import app_commands

from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService
from src.services.sync_service import SyncService
from src.utils.date_parser import format_date_pst, format_date_short, get_current_date_pst
from src.utils.date_suggestions import build_schedule_date_suggestions


class ScheduleCommand:
    """Handler for /schedule command."""

    def __init__(
        self,
        sheets_service: SheetsService,
        cache_service: CacheService,
        sync_service: SyncService,
        config: dict,
    ):
        """
        Initialize schedule command handler.

        Args:
            sheets_service: Google Sheets service instance
            cache_service: Cache service instance
            sync_service: Sync service instance
            config: Configuration dictionary from cache
        """
        self.sheets = sheets_service
        self.cache = cache_service
        self.sync = sync_service
        self.config = config
        self.logger = logging.getLogger("discord_host_scheduler.commands.schedule")

    def build_schedule_date_choices(self, current: str) -> list[app_commands.Choice[str]]:
        """
        Build autocomplete choices for schedule date selection.

        Args:
            current: Current autocomplete input

        Returns:
            List of Discord application command choices
        """
        today = get_current_date_pst()
        events_data = self.cache.get("events")
        suggestions = build_schedule_date_suggestions(events_data, today, current)

        choices: list[app_commands.Choice[str]] = []
        for value, event_date, event in suggestions:
            label = format_date_short(event_date)
            status = self._format_schedule_status(event)
            parts = [value, label]
            if status:
                parts.append(status)
            display = " • ".join(parts)
            choices.append(app_commands.Choice(name=display, value=value))
        return choices

    async def handle(
        self,
        interaction: discord.Interaction,
        date: Optional[str] = None,
        weeks: Optional[int] = None,
    ) -> None:
        """
        Handle /schedule command.

        Args:
            interaction: Discord interaction
            date: Optional specific date to check (YYYY-MM-DD format)
            weeks: Optional number of weeks to show (default from config)
        """
        # If specific date provided, show just that date
        if date:
            await self._show_specific_date(interaction, date)
            return

        # Otherwise show schedule for N weeks
        await self._show_schedule_range(interaction, weeks)

    async def _show_specific_date(self, interaction: discord.Interaction, date_str: str) -> None:
        """
        Show schedule for a specific date.

        Args:
            interaction: Discord interaction
            date_str: Date string (YYYY-MM-DD)
        """
        from src.utils.date_parser import parse_date

        # Parse date
        try:
            target_date = parse_date(date_str)
        except ValueError as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
            return

        # Get event data from cache
        event_data = self.cache.get("events", target_date.isoformat())

        # Check if cache is stale
        cache_warning = self._get_cache_warning()

        # Format response
        formatted_date = format_date_pst(target_date)

        if event_data and event_data.get("host_discord_id"):
            host_id = event_data["host_discord_id"]
            host_username = event_data.get("host_username", "Unknown")
            assigned_at = event_data.get("assigned_at", "Unknown")

            embed = discord.Embed(
                title=f"📅 Schedule for {formatted_date}",
                color=discord.Color.green(),
            )
            embed.add_field(name="Host", value=f"<@{host_id}> ({host_username})", inline=False)
            embed.add_field(name="Assigned At", value=assigned_at, inline=False)

            if event_data.get("recurring_pattern_id"):
                embed.add_field(
                    name="Recurring Pattern", value="✓ Part of recurring pattern", inline=False
                )

            if cache_warning:
                embed.set_footer(text=cache_warning)

        else:
            embed = discord.Embed(
                title=f"📅 Schedule for {formatted_date}",
                description="⚠️ **[Unassigned]** - No host assigned for this date",
                color=discord.Color.orange(),
            )

            if cache_warning:
                embed.set_footer(text=cache_warning)

        await interaction.response.send_message(embed=embed)

    async def _show_schedule_range(
        self, interaction: discord.Interaction, weeks: Optional[int]
    ) -> None:
        """
        Show schedule for a range of weeks.

        Args:
            interaction: Discord interaction
            weeks: Number of weeks to show (None = use config default)
        """
        # Get weeks from parameter or config
        if weeks is None:
            weeks = self.config.get("schedule_window_weeks", 8)

        # Validate weeks parameter
        if weeks < 1 or weeks > 52:
            await interaction.response.send_message(
                "❌ Weeks must be between 1 and 52", ephemeral=True
            )
            return

        # Calculate date range
        today = get_current_date_pst()
        end_date = today + timedelta(weeks=weeks)

        # Get events from cache
        events_data = self.cache.get("events") or {}

        # Filter events in date range
        events_in_range = []
        current_date = today

        while current_date <= end_date:
            date_str = current_date.isoformat()
            event_data = events_data.get(date_str)

            events_in_range.append(
                {
                    "date": current_date,
                    "date_str": date_str,
                    "host_id": event_data.get("host_discord_id") if event_data else None,
                    "host_username": event_data.get("host_username") if event_data else None,
                    "is_assigned": bool(event_data and event_data.get("host_discord_id")),
                }
            )

            current_date += timedelta(days=1)

        # Check if cache is stale
        cache_warning = self._get_cache_warning()

        # Format response as embed
        embed = discord.Embed(
            title=f"📅 Upcoming Host Schedule ({weeks} weeks)",
            description=f"Schedule from {format_date_pst(today)} to {format_date_pst(end_date)}",
            color=discord.Color.blue(),
        )

        # Group by week and show assigned dates
        assigned_count = 0
        unassigned_count = 0

        schedule_text = ""
        for event in events_in_range:
            if event["is_assigned"]:
                assigned_count += 1
                schedule_text += f"✅ **{format_date_pst(event['date'])}** - <@{event['host_id']}>\n"
            else:
                unassigned_count += 1
                # Only show unassigned dates (don't spam with every day)
                # Or limit to just showing count

        # Summary
        total_days = len(events_in_range)
        summary_text = (
            f"Total Days: {total_days}\n"
            f"Assigned: {assigned_count}\n"
            f"Unassigned: {unassigned_count}"
        )

        embed.add_field(name="Summary", value=summary_text, inline=False)

        # Show assigned dates (limit to avoid Discord message limits)
        if assigned_count > 0:
            # Limit to first 10 to avoid message length issues
            limited_text = "\n".join(schedule_text.split("\n")[:10])
            if assigned_count > 10:
                limited_text += f"\n... and {assigned_count - 10} more"

            embed.add_field(name="Assigned Dates", value=limited_text or "None", inline=False)
        else:
            embed.add_field(name="Assigned Dates", value="No dates assigned yet", inline=False)

        # Show unassigned warning if any
        if unassigned_count > 0:
            embed.add_field(
                name="⚠️ Unassigned Dates",
                value=f"{unassigned_count} dates need hosts",
                inline=False,
            )

        if cache_warning:
            embed.set_footer(text=cache_warning)

        await interaction.response.send_message(embed=embed)

        self.logger.info(f"User {interaction.user.id} viewed schedule ({weeks} weeks)")

    def _get_cache_warning(self) -> Optional[str]:
        """
        Get cache staleness warning if cache is stale.

        Returns:
            Warning message if cache is stale, None otherwise
        """
        if self.cache.is_stale():
            age_seconds = self.cache.get_age_seconds()
            if age_seconds:
                age_minutes = int(age_seconds / 60)
                return f"⚠️ Data may be out of date. Last synced: {age_minutes} minutes ago"
            else:
                return "⚠️ Data may be out of date. Cache not synced yet."
        return None

    @staticmethod
    def _format_schedule_status(event: Optional[Mapping[str, Any]]) -> str:
        """
        Build a short status string for schedule autocomplete suggestions.

        Args:
            event: Event dictionary (may be None)

        Returns:
            Status string describing assignment, empty string if not applicable
        """
        if not event:
            return "Unassigned"

        host_username = event.get("host_username")
        if host_username:
            return f"Host: {host_username}"

        host_id = event.get("host_discord_id")
        if host_id:
            return f"Host ID: {host_id}"

        return "Unassigned"


def register_schedule_command(
    tree: app_commands.CommandTree,
    sheets_service: SheetsService,
    cache_service: CacheService,
    sync_service: SyncService,
    config: dict,
) -> None:
    """
    Register /schedule command with Discord bot.

    Args:
        tree: Discord command tree
        sheets_service: Google Sheets service instance
        cache_service: Cache service instance
        sync_service: Sync service instance
        config: Configuration dictionary
    """
    handler = ScheduleCommand(sheets_service, cache_service, sync_service, config)

    @tree.command(name="schedule", description="View upcoming host schedule")
    @app_commands.describe(
        date="View specific date (YYYY-MM-DD format, e.g., 2025-11-11)",
        weeks="Number of weeks to show (default: 8, max: 52)",
    )
    async def schedule_command(
        interaction: discord.Interaction,
        date: Optional[str] = None,
        weeks: Optional[int] = None,
    ):
        """View upcoming host schedule."""
        await handler.handle(interaction, date, weeks)

    @schedule_command.autocomplete("date")
    async def schedule_date_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Provide autocomplete suggestions for schedule date selection."""
        try:
            return handler.build_schedule_date_choices(current)
        except Exception:
            handler.logger.exception("Failed to build schedule date suggestions")
            return []
