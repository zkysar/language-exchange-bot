"""Sync command handler."""

import logging
from typing import Any

import discord
from discord import app_commands
from gspread.exceptions import APIError

from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService
from src.services.sync_service import SyncService
from src.utils.auth import authorize_admin_command


class SyncCommand:
    """Handler for /sync command."""

    def __init__(
        self,
        sheets_service: SheetsService,
        cache_service: CacheService,
        sync_service: SyncService,
        config: dict,
    ):
        """
        Initialize sync command handler.

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
        self.logger = logging.getLogger("discord_host_scheduler.commands.sync")

    async def handle(self, interaction: discord.Interaction) -> None:
        """
        Handle /sync command.

        Args:
            interaction: Discord interaction
        """
        # Authorization check
        try:
            organizer_role_ids = self.config.get("organizer_role_ids", [])
            if not isinstance(organizer_role_ids, list):
                organizer_role_ids = []

            authorize_admin_command(interaction.user, organizer_role_ids)
        except PermissionError as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
            self.logger.warning(
                f"User {interaction.user.id} attempted to use /sync without authorization"
            )
            return

        # Acknowledge interaction (can take up to 3 seconds)
        await interaction.response.defer(ephemeral=True)

        try:
            # Perform force sync with conflict detection
            self.logger.info(f"User {interaction.user.id} initiated force sync")
            stats = self.sync.force_sync(detect_conflicts=True)

            # Build response embed
            embed = discord.Embed(
                title="🔄 Sync Complete",
                description="Successfully synchronized data from Google Sheets",
                color=discord.Color.green(),
            )

            # Add sync statistics
            embed.add_field(
                name="Records Synced",
                value=(
                    f"Events: {stats.get('events_synced', 0)}\n"
                    f"Patterns: {stats.get('patterns_synced', 0)}\n"
                    f"Configuration: {stats.get('config_synced', 0)}"
                ),
                inline=False,
            )

            # Report conflicts if any
            conflicts = stats.get("conflicts", [])
            if conflicts:
                conflict_text = ""
                for conflict in conflicts:
                    category = conflict.get("category", "unknown")
                    keys = conflict.get("keys", [])
                    conflict_text += f"**{category}**: {len(keys)} change(s)\n"
                    # Show first few keys
                    if keys:
                        sample_keys = keys[:5]
                        conflict_text += f"  - {', '.join(sample_keys[:3])}"
                        if len(keys) > 3:
                            conflict_text += f" (+{len(keys) - 3} more)"
                        conflict_text += "\n"

                embed.add_field(
                    name="⚠️ Conflicts Resolved",
                    value=conflict_text or "None",
                    inline=False,
                )
                embed.color = discord.Color.orange()

            # Add cache status
            cache_age = self.cache.get_age_seconds()
            if cache_age is not None:
                cache_minutes = int(cache_age / 60)
                embed.add_field(
                    name="Cache Status",
                    value=f"Last synced: {cache_minutes} minute(s) ago",
                    inline=False,
                )

            # Add quota usage
            quota = self.cache.get_quota_usage()
            embed.add_field(
                name="Quota Usage",
                value=(f"Reads: {quota.get('reads', 0)}\n" f"Writes: {quota.get('writes', 0)}"),
                inline=False,
            )

            await interaction.followup.send(embed=embed, ephemeral=True)
            self.logger.info(f"Sync completed for user {interaction.user.id}: {stats}")

        except APIError as e:
            # Handle Google Sheets API errors
            error_code = e.response.status_code if hasattr(e, "response") else "unknown"

            if error_code == 429:
                error_msg = (
                    "❌ Google Sheets API rate limit exceeded. " "Please try again in a few minutes."
                )
                self.logger.warning(f"Rate limit exceeded during sync: {e}")
            elif error_code == 403:
                error_msg = (
                    "❌ Google Sheets API access denied. "
                    "Please check service account permissions."
                )
                self.logger.error(f"Access denied during sync: {e}")
            else:
                error_msg = f"❌ Google Sheets API error: {str(e)}"
                self.logger.error(f"API error during sync: {e}")

            embed = discord.Embed(
                title="❌ Sync Failed",
                description=error_msg,
                color=discord.Color.red(),
            )

            # Show cache staleness warning
            if self.cache.is_stale():
                cache_age = self.cache.get_age_seconds()
                if cache_age:
                    cache_minutes = int(cache_age / 60)
                    embed.add_field(
                        name="⚠️ Warning",
                        value=(
                            f"Cache is stale ({cache_minutes} minutes old). "
                            f"Data may be out of date."
                        ),
                        inline=False,
                    )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            error_msg = f"❌ Sync failed: {str(e)}"
            self.logger.error(f"Unexpected error during sync: {e}", exc_info=True)

            embed = discord.Embed(
                title="❌ Sync Failed",
                description=error_msg,
                color=discord.Color.red(),
            )

            # Show cache staleness warning
            if self.cache.is_stale():
                cache_age = self.cache.get_age_seconds()
                if cache_age:
                    cache_minutes = int(cache_age / 60)
                    embed.add_field(
                        name="⚠️ Warning",
                        value=(
                            f"Cache is stale ({cache_minutes} minutes old). "
                            f"Data may be out of date."
                        ),
                        inline=False,
                    )

            await interaction.followup.send(embed=embed, ephemeral=True)


def register_sync_command(
    tree: app_commands.CommandTree,
    sheets_service: SheetsService,
    cache_service: CacheService,
    sync_service: SyncService,
    config: dict,
) -> None:
    """
    Register /sync command with Discord bot.

    Args:
        tree: Discord command tree
        sheets_service: Google Sheets service instance
        cache_service: Cache service instance
        sync_service: Sync service instance
        config: Configuration dictionary
    """
    handler = SyncCommand(sheets_service, cache_service, sync_service, config)

    @tree.command(name="sync", description="Force synchronization with Google Sheets (admin only)")
    async def sync_command(interaction: discord.Interaction):
        """Force synchronization with Google Sheets."""
        await handler.handle(interaction)
