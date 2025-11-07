"""Reset command handler."""

import logging
import uuid
from datetime import datetime
from typing import Any, Optional

import discord
from discord import app_commands
from discord.ui import Button, View
from gspread.exceptions import APIError

from src.models import ActionType, Outcome
from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService
from src.services.sync_service import SyncService
from src.utils.auth import authorize_admin_command
from src.utils.error_handler import get_command_context, handle_api_error, send_error_response
from src.utils.logger import log_with_context

# Global maintenance mode flag
_maintenance_mode = False


def set_maintenance_mode(enabled: bool) -> None:
    """Set maintenance mode flag."""
    global _maintenance_mode
    _maintenance_mode = enabled


def is_maintenance_mode() -> bool:
    """Check if maintenance mode is enabled."""
    return _maintenance_mode


class ResetConfirmationView(View):
    """View for confirming reset operation."""

    def __init__(
        self,
        handler: "ResetCommand",
        interaction: discord.Interaction,
    ):
        """
        Initialize reset confirmation view.

        Args:
            handler: ResetCommand handler instance
            interaction: Original Discord interaction
        """
        super().__init__(timeout=300)  # 5 minute timeout
        self.handler = handler
        self.original_interaction = interaction
        self.confirmed = False

    @discord.ui.button(label="Confirm Reset", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: Button):
        """Handle confirmation button click."""
        if interaction.user.id != self.original_interaction.user.id:
            await interaction.response.send_message(
                "❌ Only the user who started this command can confirm it.", ephemeral=True
            )
            return

        self.confirmed = True
        await interaction.response.defer()

        try:
            await self.handler._execute_reset(interaction)
        except Exception as e:
            if isinstance(e, APIError):
                await handle_api_error(interaction, e, self.handler.logger, "reset operation")
            else:
                context = get_command_context(interaction, "reset")
                await send_error_response(
                    interaction,
                    "Reset failed. Please check the logs for details.",
                    self.handler.logger,
                    e,
                    context,
                )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        """Handle cancel button click."""
        if interaction.user.id != self.original_interaction.user.id:
            await interaction.response.send_message(
                "❌ Only the user who started this command can cancel it.", ephemeral=True
            )
            return

        await interaction.response.edit_message(content="❌ Reset operation cancelled.", view=None)
        self.stop()


class ResetCommand:
    """Handler for /reset command."""

    def __init__(
        self,
        sheets_service: SheetsService,
        cache_service: CacheService,
        sync_service: SyncService,
        config: dict,
    ):
        """
        Initialize reset command handler.

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
        self.logger = logging.getLogger("discord_host_scheduler.commands.reset")

    async def handle(self, interaction: discord.Interaction, confirm: bool = False) -> None:
        """
        Handle /reset command.

        Args:
            interaction: Discord interaction
            confirm: Whether to confirm reset immediately (for confirmation flow)
        """
        # Authorization check
        try:
            organizer_role_ids = self.config.get("organizer_role_ids", [])
            if not isinstance(organizer_role_ids, list):
                organizer_role_ids = []

            authorize_admin_command(interaction.user, organizer_role_ids)
        except PermissionError as e:
            context = get_command_context(interaction, "reset")
            await send_error_response(interaction, str(e), self.logger, e, context)
            return

        # Check maintenance mode
        if is_maintenance_mode():
            await interaction.response.send_message(
                "⚠️ **Maintenance Mode Active**\n\n"
                "The bot is currently in maintenance mode. Please wait for the reset operation to complete.",
                ephemeral=True,
            )
            return

        if confirm:
            # Execute reset immediately (called from confirmation view)
            await interaction.response.defer(ephemeral=True)
            try:
                await self._execute_reset(interaction)
            except Exception as e:
                if isinstance(e, APIError):
                    await handle_api_error(interaction, e, self.logger, "reset operation")
                else:
                    context = get_command_context(interaction, "reset")
                    await send_error_response(
                        interaction,
                        "Reset failed. Please check the logs for details.",
                        self.logger,
                        e,
                        context,
                    )
        else:
            # Show reset instructions and confirmation
            await self._show_reset_instructions(interaction)

    async def _show_reset_instructions(self, interaction: discord.Interaction) -> None:
        """
        Show reset instructions and confirmation prompt.

        Args:
            interaction: Discord interaction
        """
        embed = discord.Embed(
            title="🔄 Database Reset Instructions",
            description=(
                "This command will reset the bot's local database to recover from "
                "corruption or data inconsistency."
            ),
            color=discord.Color.orange(),
        )

        embed.add_field(
            name="What Reset Does",
            value=(
                "• Clears local cache file (cache.json)\n"
                "• Reinitializes all data from Google Sheets (authoritative source)\n"
                "• Verifies data integrity after completion\n"
                "• Creates audit log entry for the reset action\n"
                "• Prevents user interactions during reset operation (maintenance mode)"
            ),
            inline=False,
        )

        embed.add_field(
            name="Before You Proceed",
            value=(
                "⚠️ **Important**:\n"
                "1. Verify that Google Sheets contains the correct data (it's the source of truth)\n"
                "2. Ensure no critical operations are in progress\n"
                "3. The bot will be unavailable for a few moments during reset\n"
                "4. All local cache will be lost (data will be reloaded from Google Sheets)"
            ),
            inline=False,
        )

        embed.add_field(
            name="When to Use Reset",
            value=(
                "Reset should be used as a last resort when:\n"
                "• Cache is corrupted and `/sync` doesn't fix it\n"
                "• Data inconsistency persists after manual Google Sheets edits\n"
                "• Bot is experiencing persistent data errors\n"
                "\n"
                "**Note**: Most issues can be resolved with `/sync` or manual Google Sheets edits."
            ),
            inline=False,
        )

        embed.set_footer(text="Click 'Confirm Reset' below to proceed, or 'Cancel' to abort.")

        view = ResetConfirmationView(self, interaction)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _execute_reset(self, interaction: discord.Interaction) -> None:
        """
        Execute the reset operation.

        Args:
            interaction: Discord interaction
        """
        global _maintenance_mode

        try:
            # Enable maintenance mode
            set_maintenance_mode(True)
            self.logger.info(f"User {interaction.user.id} initiated database reset")

            # Send initial response
            embed = discord.Embed(
                title="🔄 Database Reset in Progress",
                description="The reset operation has started. This may take a few moments.",
                color=discord.Color.blue(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

            # Step 1: Clear cache
            self.logger.info("Step 1: Clearing cache")
            try:
                self.cache.clear()
                self.logger.info("Cache cleared successfully")
            except Exception as e:
                self.logger.error(f"Failed to clear cache: {e}")
                raise

            # Step 2: Verify Google Sheets connectivity and data integrity
            self.logger.info("Step 2: Verifying Google Sheets connectivity")
            try:
                self._verify_data_integrity()
                self.logger.info("Data integrity verification passed")
            except Exception as e:
                self.logger.error(f"Data integrity verification failed: {e}")
                raise

            # Step 3: Reinitialize from Google Sheets
            self.logger.info("Step 3: Reinitializing from Google Sheets")
            try:
                stats = self.sync.sync_all(detect_conflicts=False)
                self.logger.info(f"Reinitialization completed: {stats}")
            except Exception as e:
                self.logger.error(f"Reinitialization failed: {e}")
                raise

            # Step 4: Verify data integrity after reset
            self.logger.info("Step 4: Verifying data integrity after reset")
            try:
                self._verify_data_integrity()
                self.logger.info("Post-reset data integrity verification passed")
            except Exception as e:
                self.logger.error(f"Post-reset data integrity verification failed: {e}")
                raise

            # Step 5: Create audit log entry
            self.logger.info("Step 5: Creating audit log entry")
            try:
                self._create_audit_entry(
                    user_discord_id=str(interaction.user.id),
                    outcome=Outcome.SUCCESS,
                    metadata={
                        "events_synced": stats.get("events_synced", 0),
                        "patterns_synced": stats.get("patterns_synced", 0),
                        "config_synced": stats.get("config_synced", 0),
                    },
                )
            except Exception as e:
                # Log error but don't fail the reset
                self.logger.warning(f"Failed to create audit entry: {e}")

            # Success response
            success_embed = discord.Embed(
                title="✅ Database Reset Complete",
                description="The database has been successfully reset and reinitialized from Google Sheets.",
                color=discord.Color.green(),
            )

            success_embed.add_field(
                name="Reset Statistics",
                value=(
                    f"Events synced: {stats.get('events_synced', 0)}\n"
                    f"Patterns synced: {stats.get('patterns_synced', 0)}\n"
                    f"Configuration synced: {stats.get('config_synced', 0)}"
                ),
                inline=False,
            )

            success_embed.add_field(
                name="Next Steps",
                value=(
                    "• Verify the data using `/schedule` command\n"
                    "• Check that all dates and patterns are correct\n"
                    "• Monitor for any issues in the next few minutes"
                ),
                inline=False,
            )

            await interaction.followup.send(embed=success_embed, ephemeral=True)

            # Structured logging for state-changing operation
            log_with_context(
                self.logger,
                "info",
                "Database reset completed successfully",
                get_command_context(
                    interaction,
                    "reset",
                    events_synced=stats.get("events_synced", 0),
                    patterns_synced=stats.get("patterns_synced", 0),
                    config_synced=stats.get("config_synced", 0),
                    outcome="success",
                ),
            )

        except Exception as e:
            # Create audit entry for failure
            try:
                self._create_audit_entry(
                    user_discord_id=str(interaction.user.id),
                    outcome=Outcome.FAILURE,
                    error_message=str(e),
                )
            except Exception as audit_error:
                self.logger.warning(f"Failed to create audit entry for failure: {audit_error}")

            # Re-raise to be handled by caller
            raise
        finally:
            # Disable maintenance mode
            set_maintenance_mode(False)
            self.logger.info("Maintenance mode disabled")

    def _verify_data_integrity(self) -> None:
        """
        Verify data integrity by checking required sheets exist and contain valid data.

        Raises:
            ValueError: If data integrity check fails
        """
        required_sheets = [
            self.sheets.SHEET_SCHEDULE,
            self.sheets.SHEET_RECURRING_PATTERNS,
            self.sheets.SHEET_AUDIT_LOG,
            self.sheets.SHEET_CONFIGURATION,
        ]

        for sheet_name in required_sheets:
            try:
                sheet = self.sheets.get_sheet(sheet_name)
                # Try to read first row to verify sheet is accessible
                sheet.get("A1")
                self.logger.debug(f"Sheet '{sheet_name}' verified")
            except Exception as e:
                raise ValueError(
                    f"Data integrity check failed: Sheet '{sheet_name}' is not accessible or missing: {e}"
                )

        # Verify configuration has required settings
        try:
            config_records = self.sheets.read_all_records(self.sheets.SHEET_CONFIGURATION)
            self.cache.increment_quota("reads", 1)

            # Check for at least some configuration entries
            if not config_records:
                self.logger.warning("Configuration sheet is empty, but continuing...")

        except Exception as e:
            raise ValueError(f"Failed to verify configuration: {e}")

    def _create_audit_entry(
        self,
        user_discord_id: str,
        outcome: Outcome,
        error_message: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Create audit log entry for reset operation.

        Args:
            user_discord_id: Discord ID of user performing reset
            outcome: Success or failure
            error_message: Error message if failed
            metadata: Additional metadata (e.g., sync statistics)
        """
        try:
            entry_id = str(uuid.uuid4())
            now = datetime.now()

            # Convert metadata to JSON string
            metadata_json = "{}"
            if metadata:
                import json

                metadata_json = json.dumps(metadata)

            row_data = [
                entry_id,
                now.isoformat(),
                ActionType.RESET.value,
                user_discord_id,
                "",  # target_user_discord_id (not applicable for reset)
                "",  # event_date (not applicable for reset)
                "",  # recurring_pattern_id (not applicable for reset)
                outcome.value,
                error_message or "",
                metadata_json,
            ]

            self.sheets.append_row(self.sheets.SHEET_AUDIT_LOG, row_data)
            self.cache.increment_quota("writes", 1)

            self.logger.info(f"Created audit entry for reset: {entry_id}")

        except Exception as e:
            self.logger.error(f"Failed to create audit entry: {e}", exc_info=True)


def register_reset_command(
    tree: app_commands.CommandTree,
    sheets_service: SheetsService,
    cache_service: CacheService,
    sync_service: SyncService,
    config: dict,
) -> None:
    """
    Register /reset command with Discord bot.

    Args:
        tree: Discord command tree
        sheets_service: Google Sheets service instance
        cache_service: Cache service instance
        sync_service: Sync service instance
        config: Configuration dictionary
    """
    handler = ResetCommand(sheets_service, cache_service, sync_service, config)

    @tree.command(
        name="reset",
        description="Display instructions for safely resetting the database (admin only)",
    )
    async def reset_command(interaction: discord.Interaction):
        """Display reset instructions and confirmation prompt."""
        await handler.handle(interaction, confirm=False)
