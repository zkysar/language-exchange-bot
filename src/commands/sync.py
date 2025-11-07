"""Sync command handler."""

import logging

import discord
from discord import app_commands
from gspread.exceptions import APIError

from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService
from src.services.sync_service import SyncService
from src.utils.auth import authorize_admin_command
from src.utils.error_handler import get_command_context, handle_api_error, send_error_response
from src.utils.logger import log_with_context

# Import maintenance mode check
try:
    from src.commands.reset import is_maintenance_mode
except ImportError:
    # Fallback if reset module not available
    def is_maintenance_mode() -> bool:
        return False


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
        # Check maintenance mode
        if is_maintenance_mode():
            await interaction.response.send_message(
                "⚠️ **Maintenance Mode Active**\n\n"
                "The bot is currently in maintenance mode. "
                "Please wait for the operation to complete.",
                ephemeral=True,
            )
            return

        # Authorization check
        try:
            # Ensure we have a proper guild member with roles
            if interaction.guild is None:
                await interaction.response.send_message(
                    "❌ This command can only be used in a server.",
                    ephemeral=True,
                )
                return

            # Fetch the full member object from the guild to ensure roles are populated
            member = interaction.guild.get_member(interaction.user.id)
            if member is None:
                try:
                    member = await interaction.guild.fetch_member(interaction.user.id)
                except discord.NotFound:
                    await interaction.response.send_message(
                        "❌ Could not find your membership in this server.",
                        ephemeral=True,
                    )
                    return
                except Exception as fetch_error:
                    self.logger.error(f"Failed to fetch member: {fetch_error}", exc_info=True)
                    await interaction.response.send_message(
                        f"❌ Error fetching member information: {fetch_error}",
                        ephemeral=True,
                    )
                    return

            organizer_role_ids = self.config.get("organizer_role_ids", [])
            if not isinstance(organizer_role_ids, list):
                organizer_role_ids = []

            authorize_admin_command(member, organizer_role_ids)
        except PermissionError as e:
            context = get_command_context(interaction, "sync")
            await send_error_response(interaction, str(e), self.logger, e, context)
            return
        except Exception as e:
            self.logger.error(f"Unexpected error in authorization: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ An unexpected error occurred: {e}",
                ephemeral=True,
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

            # Structured logging for state-changing operation
            log_with_context(
                self.logger,
                "info",
                "Sync completed successfully",
                get_command_context(
                    interaction,
                    "sync",
                    events_synced=stats.get("events_synced", 0),
                    patterns_synced=stats.get("patterns_synced", 0),
                    config_synced=stats.get("config_synced", 0),
                    conflicts_resolved=len(conflicts),
                    outcome="success",
                ),
            )

        except APIError as e:
            # Handle Google Sheets API errors using consistent error handler
            context = get_command_context(interaction, "sync")
            await handle_api_error(interaction, e, self.logger, "sync operation", context)

        except Exception as e:
            context = get_command_context(interaction, "sync")
            await send_error_response(
                interaction,
                "Sync failed. Please try again.",
                self.logger,
                e,
                context,
            )


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
