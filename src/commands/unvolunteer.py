"""Unvolunteer command handler."""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands

from src.models import ActionType, Outcome
from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService
from src.services.sync_service import SyncService
from src.utils.auth import authorize_proxy_action
from src.utils.date_parser import format_date_pst, validate_date_format_and_future
from src.utils.error_handler import get_command_context, handle_api_error, send_error_response
from src.utils.logger import log_with_context


class UnvolunteerCommand:
    """Handler for /unvolunteer command."""

    def __init__(
        self,
        sheets_service: SheetsService,
        cache_service: CacheService,
        sync_service: SyncService,
        config: dict,
    ):
        """
        Initialize unvolunteer command handler.

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
        self.logger = logging.getLogger("discord_host_scheduler.commands.unvolunteer")

    async def handle(
        self,
        interaction: discord.Interaction,
        date: str,
        user: Optional[discord.Member] = None,
    ) -> None:
        """
        Handle /unvolunteer command.

        Args:
            interaction: Discord interaction
            date: Date to unvolunteer from (YYYY-MM-DD format)
            user: Optional user to unvolunteer on behalf of (requires host-privileged role)
        """
        # Determine target user (proxy action or self)
        target_user = user if user else interaction.user
        target_discord_id = str(target_user.id)

        # Authorization check for proxy actions
        try:
            host_privileged_role_ids = self.config.get("host_privileged_role_ids", [])
            authorize_proxy_action(
                interaction.user, target_discord_id if user else None, host_privileged_role_ids
            )
        except PermissionError as e:
            context = get_command_context(
                interaction, "unvolunteer", date=date, target_user_id=target_discord_id
            )
            await send_error_response(interaction, str(e), self.logger, e, context)
            self._create_audit_entry(
                action_type=ActionType.UNVOLUNTEER,
                user_discord_id=str(interaction.user.id),
                target_user_discord_id=target_discord_id,
                event_date=None,
                outcome=Outcome.FAILURE,
                error_message=str(e),
            )
            return

        # Date validation
        try:
            validated_date = validate_date_format_and_future(date)
        except ValueError as e:
            context = get_command_context(
                interaction, "unvolunteer", date=date, target_user_id=target_discord_id
            )
            await send_error_response(interaction, str(e), self.logger, e, context)
            self._create_audit_entry(
                action_type=ActionType.UNVOLUNTEER,
                user_discord_id=str(interaction.user.id),
                target_user_discord_id=target_discord_id,
                event_date=None,
                outcome=Outcome.FAILURE,
                error_message=str(e),
            )
            return

        date_str = validated_date.isoformat()

        # Check if target user is assigned to date
        existing_event = self.cache.get("events", date_str)
        if not existing_event or existing_event.get("host_discord_id") != target_discord_id:
            formatted_date_str = format_date_pst(validated_date)
            error_msg = (
                f"<@{target_discord_id}> is not assigned to host on {formatted_date_str}. "
                f"Please verify the date and try again."
            )
            await interaction.response.send_message(f"❌ {error_msg}", ephemeral=True)

            self._create_audit_entry(
                action_type=ActionType.UNVOLUNTEER,
                user_discord_id=str(interaction.user.id),
                target_user_discord_id=target_discord_id,
                event_date=validated_date,
                outcome=Outcome.FAILURE,
                error_message="User not assigned to date",
            )
            return

        # Remove host assignment from date
        try:
            await self._remove_host_from_date(
                date_str=date_str,
                validated_date=validated_date,
                target_user=target_user,
                assigned_by=str(interaction.user.id),
            )

            # Send success message
            formatted_date = format_date_pst(validated_date)
            if user:
                # Proxy action
                message = (
                    f"✅ Successfully removed <@{target_discord_id}> "
                    f"from hosting on **{formatted_date}**\n"
                    f"Removed by: <@{interaction.user.id}>"
                )
            else:
                # Self removal
                message = (
                    f"✅ You've successfully unvolunteered from hosting on **{formatted_date}**"
                )

            await interaction.response.send_message(message)

            # Create audit entry
            self._create_audit_entry(
                action_type=ActionType.UNVOLUNTEER,
                user_discord_id=str(interaction.user.id),
                target_user_discord_id=target_discord_id,
                event_date=validated_date,
                outcome=Outcome.SUCCESS,
                error_message=None,
            )

            # Structured logging for state-changing operation
            log_with_context(
                self.logger,
                "info",
                "Unvolunteer removal successful",
                get_command_context(
                    interaction,
                    "unvolunteer",
                    date=date_str,
                    target_user_id=target_discord_id,
                    outcome="success",
                ),
            )

        except Exception as e:
            from gspread.exceptions import APIError

            if isinstance(e, APIError):
                await handle_api_error(
                    interaction,
                    e,
                    self.logger,
                    "unvolunteer removal",
                    get_command_context(
                        interaction, "unvolunteer", date=date_str, target_user_id=target_discord_id
                    ),
                )
            else:
                context = get_command_context(
                    interaction, "unvolunteer", date=date_str, target_user_id=target_discord_id
                )
                await send_error_response(
                    interaction,
                    "Failed to remove host assignment. Please try again.",
                    self.logger,
                    e,
                    context,
                )

            self._create_audit_entry(
                action_type=ActionType.UNVOLUNTEER,
                user_discord_id=str(interaction.user.id),
                target_user_discord_id=target_discord_id,
                event_date=validated_date,
                outcome=Outcome.FAILURE,
                error_message=str(e),
            )

    async def _remove_host_from_date(
        self,
        date_str: str,
        validated_date,
        target_user: discord.Member,
        assigned_by: str,
    ) -> None:
        """
        Remove host assignment from date in Google Sheets and cache.

        Args:
            date_str: Date string (YYYY-MM-DD)
            validated_date: Validated date object
            target_user: Discord member being removed
            assigned_by: Discord ID of user making removal (for proxy actions)
        """
        # Find row in Google Sheets
        existing_row = self.sheets.find_row(self.sheets.SHEET_SCHEDULE, 1, date_str)

        if existing_row:
            # Clear host assignment columns (B-G):
            # host_discord_id, host_username, recurring_pattern_id,
            # assigned_at, assigned_by, notes
            # Keep the date column (A) intact
            clear_data = [
                "",  # host_discord_id
                "",  # host_username
                "",  # recurring_pattern_id
                "",  # assigned_at
                "",  # assigned_by
                "",  # notes
            ]
            self.sheets.update_range(
                self.sheets.SHEET_SCHEDULE, f"B{existing_row}:G{existing_row}", [clear_data]
            )
        else:
            # Row doesn't exist, nothing to remove
            self.logger.warning(f"Date {date_str} not found in Schedule sheet")

        # Increment quota
        self.cache.increment_quota("writes", 1)

        # Update cache - clear assignment but keep date entry
        self.cache.set(
            "events",
            date_str,
            {
                "host_discord_id": None,
                "host_username": None,
                "recurring_pattern_id": None,
                "assigned_at": None,
                "assigned_by": None,
                "notes": None,
            },
        )

        self.logger.info(f"Removed {target_user.id} from {date_str} in Sheets and cache")

    def _create_audit_entry(
        self,
        action_type: ActionType,
        user_discord_id: str,
        target_user_discord_id: str,
        event_date,
        outcome: Outcome,
        error_message: Optional[str],
    ) -> None:
        """
        Create audit log entry in Google Sheets.

        Args:
            action_type: Type of action
            user_discord_id: Discord ID of user performing action
            target_user_discord_id: Discord ID of affected user (for proxy actions)
            event_date: Date affected by action
            outcome: Success or failure
            error_message: Error message if failed
        """
        try:
            entry_id = str(uuid.uuid4())
            now = datetime.now()

            # For proxy actions, include assigned_by in metadata
            metadata = {}
            if user_discord_id != target_user_discord_id:
                metadata["assigned_by"] = user_discord_id

            row_data = [
                entry_id,
                now.isoformat(),
                action_type.value,
                user_discord_id,
                target_user_discord_id,
                event_date.isoformat() if event_date else "",
                "",  # recurring_pattern_id
                outcome.value,
                error_message or "",
                json.dumps(metadata),  # metadata (JSON string)
            ]

            self.sheets.append_row(self.sheets.SHEET_AUDIT_LOG, row_data)
            self.cache.increment_quota("writes", 1)

            self.logger.info(f"Created audit entry: {entry_id}")

        except Exception as e:
            self.logger.error(f"Failed to create audit entry: {e}", exc_info=True)


def register_unvolunteer_command(
    tree: app_commands.CommandTree,
    sheets_service: SheetsService,
    cache_service: CacheService,
    sync_service: SyncService,
    config: dict,
) -> None:
    """
    Register /unvolunteer command with Discord bot.

    Args:
        tree: Discord command tree
        sheets_service: Google Sheets service instance
        cache_service: Cache service instance
        sync_service: Sync service instance
        config: Configuration dictionary
    """
    handler = UnvolunteerCommand(sheets_service, cache_service, sync_service, config)

    @tree.command(
        name="unvolunteer", description="Cancel your hosting commitment for a specific date"
    )
    @app_commands.describe(
        date="Date to unvolunteer from (YYYY-MM-DD format, e.g., 2025-11-11)",
        user="User to unvolunteer on behalf of (requires host-privileged role)",
    )
    async def unvolunteer_command(
        interaction: discord.Interaction,
        date: str,
        user: Optional[discord.Member] = None,
    ):
        """Cancel hosting commitment for a specific date."""
        await handler.handle(interaction, date, user)
