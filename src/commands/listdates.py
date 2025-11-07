"""Listdates command handler."""

import logging
from datetime import timedelta
from typing import Optional

import discord
from discord import app_commands

from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService
from src.services.sync_service import SyncService
from src.utils.date_parser import format_date_pst, get_current_date_pst


class ListDatesCommand:
    """Handler for /listdates command."""

    def __init__(
        self,
        sheets_service: SheetsService,
        cache_service: CacheService,
        sync_service: SyncService,
        config: dict,
    ):
        """
        Initialize listdates command handler.

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
        self.logger = logging.getLogger("discord_host_scheduler.commands.listdates")

    async def handle(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
    ) -> None:
        """
        Handle /listdates command.

        Args:
            interaction: Discord interaction
            user: Optional user to list dates for (defaults to command user)
        """
        # Determine target user (default to command user)
        target_user = user if user else interaction.user
        target_discord_id = str(target_user.id)

        # Get events from cache
        events_data = self.cache.get("events") or {}

        # Calculate date range (next 12 weeks)
        today = get_current_date_pst()
        end_date = today + timedelta(weeks=12)

        # Filter events assigned to target user within date range
        user_dates = []
        current_date = today

        while current_date <= end_date:
            date_str = current_date.isoformat()
            event_data = events_data.get(date_str)

            if event_data and event_data.get("host_discord_id") == target_discord_id:
                recurring_pattern_id = event_data.get("recurring_pattern_id")
                assigned_at = event_data.get("assigned_at", "Unknown")
                notes = event_data.get("notes")

                user_dates.append(
                    {
                        "date": current_date,
                        "date_str": date_str,
                        "recurring_pattern_id": recurring_pattern_id,
                        "assigned_at": assigned_at,
                        "notes": notes,
                    }
                )

            current_date += timedelta(days=1)

        # Check if cache is stale
        cache_warning = self._get_cache_warning()

        # Format response as embed
        if target_user.id == interaction.user.id:
            title = "📅 Your Upcoming Hosting Dates"
            description = f"Dates you're scheduled to host (next 12 weeks)"
        else:
            title = f"📅 Upcoming Hosting Dates for {target_user.display_name}"
            description = f"Dates {target_user.display_name} is scheduled to host (next 12 weeks)"

        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blue(),
        )

        if not user_dates:
            embed.add_field(
                name="No Dates Found",
                value=f"{'You have' if target_user.id == interaction.user.id else f'{target_user.display_name} has'} no upcoming hosting dates in the next 12 weeks.",
                inline=False,
            )
        else:
            # Group dates by recurring pattern
            recurring_dates = []
            single_dates = []

            for date_info in user_dates:
                if date_info["recurring_pattern_id"]:
                    recurring_dates.append(date_info)
                else:
                    single_dates.append(date_info)

            # Format recurring pattern dates
            if recurring_dates:
                # Get recurring pattern info from cache
                recurring_patterns = self.cache.get("recurring_patterns") or {}
                pattern_groups = {}

                for date_info in recurring_dates:
                    pattern_id = date_info["recurring_pattern_id"]
                    pattern_data = recurring_patterns.get(pattern_id, {})

                    if pattern_id not in pattern_groups:
                        pattern_description = pattern_data.get(
                            "pattern_description", "Unknown pattern"
                        )
                        pattern_groups[pattern_id] = {
                            "description": pattern_description,
                            "dates": [],
                        }

                    pattern_groups[pattern_id]["dates"].append(date_info)

                # Add recurring pattern sections
                for pattern_id, pattern_info in pattern_groups.items():
                    dates_list = pattern_info["dates"]
                    dates_text = "\n".join(
                        [
                            f"• {format_date_pst(d['date'])}"
                            for d in sorted(dates_list, key=lambda x: x["date"])
                        ]
                    )

                    embed.add_field(
                        name=f"🔄 {pattern_info['description']} ({len(dates_list)} date(s))",
                        value=dates_text,
                        inline=False,
                    )

            # Format single dates
            if single_dates:
                dates_text = "\n".join(
                    [
                        f"• {format_date_pst(d['date'])}"
                        for d in sorted(single_dates, key=lambda x: x["date"])
                    ]
                )

                embed.add_field(
                    name=f"📌 Single Dates ({len(single_dates)} date(s))",
                    value=dates_text,
                    inline=False,
                )

            # Summary
            total_count = len(user_dates)
            recurring_count = len(recurring_dates)
            single_count = len(single_dates)

            summary_text = (
                f"**Total:** {total_count} date(s)\n"
                f"**Recurring:** {recurring_count} date(s)\n"
                f"**Single:** {single_count} date(s)"
            )

            embed.add_field(name="Summary", value=summary_text, inline=False)

        if cache_warning:
            embed.set_footer(text=cache_warning)

        await interaction.response.send_message(embed=embed)

        self.logger.info(
            f"User {interaction.user.id} listed dates for {target_discord_id} "
            f"({len(user_dates)} dates found)"
        )

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


def register_listdates_command(
    tree: app_commands.CommandTree,
    sheets_service: SheetsService,
    cache_service: CacheService,
    sync_service: SyncService,
    config: dict,
) -> None:
    """
    Register /listdates command with Discord bot.

    Args:
        tree: Discord command tree
        sheets_service: Google Sheets service instance
        cache_service: Cache service instance
        sync_service: Sync service instance
        config: Configuration dictionary
    """
    handler = ListDatesCommand(sheets_service, cache_service, sync_service, config)

    @tree.command(name="listdates", description="View all upcoming hosting dates for a user")
    @app_commands.describe(
        user="User to list dates for (defaults to yourself)",
    )
    async def listdates_command(
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
    ):
        """View all upcoming hosting dates for a user."""
        await handler.handle(interaction, user)
