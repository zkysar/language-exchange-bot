"""Volunteer command handler."""

import logging
import uuid
from datetime import date, datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ui import Button, View

from src.models import ActionType, Outcome
from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService
from src.services.sync_service import SyncService
from src.utils.auth import authorize_proxy_action
from src.utils.date_parser import format_date_pst, validate_date_format_and_future
from src.utils.error_handler import get_command_context, handle_api_error, send_error_response
from src.utils.logger import log_with_context
from src.utils.pattern_parser import (
    generate_dates_from_pattern,
    parse_pattern_description,
    pattern_rule_to_json,
)


class ConfirmationView(View):
    """View for confirming recurring pattern assignment."""

    def __init__(
        self,
        handler: "VolunteerCommand",
        interaction: discord.Interaction,
        target_user: discord.Member,
        pattern_description: str,
        pattern_dict: dict,
        dates: list[date],
        conflicts: list[date],
        valid_dates: list[date],
    ):
        """
        Initialize confirmation view.

        Args:
            handler: VolunteerCommand handler instance
            interaction: Original Discord interaction
            target_user: Target user to assign
            pattern_description: Human-readable pattern description
            pattern_dict: Parsed pattern dictionary
            dates: All generated dates
            conflicts: List of conflicted dates
            valid_dates: List of valid (non-conflicted) dates
        """
        super().__init__(timeout=300)  # 5 minute timeout
        self.handler = handler
        self.original_interaction = interaction
        self.target_user = target_user
        self.pattern_description = pattern_description
        self.pattern_dict = pattern_dict
        self.dates = dates
        self.conflicts = conflicts
        self.valid_dates = valid_dates
        self.confirmed = False

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
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
            assigned_by_id = str(self.original_interaction.user.id)
            await self.handler._execute_recurring_assignment(
                interaction=interaction,
                target_user=self.target_user,
                pattern_description=self.pattern_description,
                pattern_dict=self.pattern_dict,
                valid_dates=self.valid_dates,
                conflicts=self.conflicts,
                assigned_by_id=assigned_by_id,
            )
        except Exception as e:
            from gspread.exceptions import APIError

            if isinstance(e, APIError):
                await handle_api_error(
                    interaction, e, self.handler.logger, "recurring pattern assignment"
                )
            else:
                context = get_command_context(
                    interaction, "volunteer_recurring", pattern=self.pattern_description
                )
                await send_error_response(
                    interaction,
                    "Failed to assign recurring pattern. Please try again.",
                    self.handler.logger,
                    e,
                    context,
                )

        # Disable buttons
        for item in self.children:
            item.disabled = True
        await self.original_interaction.edit_original_response(view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        """Handle cancellation button click."""
        if interaction.user.id != self.original_interaction.user.id:
            await interaction.response.send_message(
                "❌ Only the user who started this command can cancel it.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            "❌ Recurring pattern assignment cancelled.", ephemeral=True
        )

        # Disable buttons
        for item in self.children:
            item.disabled = True
        await self.original_interaction.edit_original_response(view=self)
        self.stop()


class VolunteerCommand:
    """Handler for /volunteer command."""

    def __init__(
        self,
        sheets_service: SheetsService,
        cache_service: CacheService,
        sync_service: SyncService,
        config: dict,
    ):
        """
        Initialize volunteer command handler.

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
        self.logger = logging.getLogger("discord_host_scheduler.commands.volunteer")

    async def handle(
        self,
        interaction: discord.Interaction,
        date: str,
        user: Optional[discord.Member] = None,
    ) -> None:
        """
        Handle /volunteer command.

        Args:
            interaction: Discord interaction
            date: Date to volunteer for (YYYY-MM-DD format)
            user: Optional user to volunteer on behalf of (requires host-privileged role)
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
                interaction, "volunteer", date=date, target_user_id=target_discord_id
            )
            await send_error_response(interaction, str(e), self.logger, e, context)
            self._create_audit_entry(
                action_type=ActionType.VOLUNTEER,
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
                interaction, "volunteer", date=date, target_user_id=target_discord_id
            )
            await send_error_response(interaction, str(e), self.logger, e, context)
            self._create_audit_entry(
                action_type=ActionType.VOLUNTEER,
                user_discord_id=str(interaction.user.id),
                target_user_discord_id=target_discord_id,
                event_date=None,
                outcome=Outcome.FAILURE,
                error_message=str(e),
            )
            return

        date_str = validated_date.isoformat()

        # Check for existing assignment (conflict detection)
        existing_event = self.cache.get("events", date_str)
        if existing_event and existing_event.get("host_discord_id"):
            existing_host_id = existing_event["host_discord_id"]
            existing_host_username = existing_event.get("host_username", "Unknown user")

            error_msg = (
                f"Date {format_date_pst(validated_date)} is already assigned to "
                f"<@{existing_host_id}> ({existing_host_username}). "
                f"Please choose a different date."
            )
            await interaction.response.send_message(f"❌ {error_msg}", ephemeral=True)

            self._create_audit_entry(
                action_type=ActionType.VOLUNTEER,
                user_discord_id=str(interaction.user.id),
                target_user_discord_id=target_discord_id,
                event_date=validated_date,
                outcome=Outcome.FAILURE,
                error_message="Date already assigned (conflict)",
            )
            return

        # Assign host to date
        try:
            await self._assign_host_to_date(
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
                    f"✅ Successfully assigned <@{target_discord_id}> "
                    f"to host on **{formatted_date}**\n"
                    f"Assigned by: <@{interaction.user.id}>"
                )
            else:
                # Self assignment
                message = f"✅ You've successfully volunteered to host on **{formatted_date}**"

            await interaction.response.send_message(message)

            # Create audit entry
            self._create_audit_entry(
                action_type=ActionType.VOLUNTEER,
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
                "Volunteer assignment successful",
                get_command_context(
                    interaction,
                    "volunteer",
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
                    "volunteer assignment",
                    get_command_context(
                        interaction, "volunteer", date=date_str, target_user_id=target_discord_id
                    ),
                )
            else:
                context = get_command_context(
                    interaction, "volunteer", date=date_str, target_user_id=target_discord_id
                )
                await send_error_response(
                    interaction,
                    "Failed to assign host. Please try again.",
                    self.logger,
                    e,
                    context,
                )

            self._create_audit_entry(
                action_type=ActionType.VOLUNTEER,
                user_discord_id=str(interaction.user.id),
                target_user_discord_id=target_discord_id,
                event_date=validated_date,
                outcome=Outcome.FAILURE,
                error_message=str(e),
            )

    async def handle_recurring(
        self,
        interaction: discord.Interaction,
        pattern: str,
        user: Optional[discord.Member] = None,
    ) -> None:
        """
        Handle /volunteer recurring command.

        Args:
            interaction: Discord interaction
            pattern: Pattern description (e.g., "every 2nd Tuesday")
            user: Optional user to volunteer on behalf of (requires host-privileged role)
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
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
            self._create_audit_entry(
                action_type=ActionType.VOLUNTEER_RECURRING,
                user_discord_id=str(interaction.user.id),
                target_user_discord_id=target_discord_id,
                event_date=None,
                outcome=Outcome.FAILURE,
                error_message=str(e),
                recurring_pattern_id=None,
            )
            return

        # Parse pattern description
        try:
            pattern_dict = parse_pattern_description(pattern)
        except ValueError as e:
            await interaction.response.send_message(
                f"❌ Invalid pattern: {str(e)}\n\n"
                f"Supported formats:\n"
                f"- 'every Nth weekday' (e.g., 'every 2nd Tuesday', 'every 1st Friday')\n"
                f"- 'monthly' (1st of every month)\n"
                f"- 'biweekly' (every 2 weeks)\n"
                f"- 'weekly' (every week)",
                ephemeral=True,
            )
            self._create_audit_entry(
                action_type=ActionType.VOLUNTEER_RECURRING,
                user_discord_id=str(interaction.user.id),
                target_user_discord_id=target_discord_id,
                event_date=None,
                outcome=Outcome.FAILURE,
                error_message=f"Invalid pattern: {str(e)}",
                recurring_pattern_id=None,
            )
            return

        # Generate dates for next 3 months
        try:
            start_date = date.today()
            end_date = None  # Indefinite pattern
            dates = generate_dates_from_pattern(pattern_dict, start_date, end_date, months=3)
        except ValueError as e:
            await interaction.response.send_message(
                f"❌ Failed to generate dates from pattern: {str(e)}", ephemeral=True
            )
            self._create_audit_entry(
                action_type=ActionType.VOLUNTEER_RECURRING,
                user_discord_id=str(interaction.user.id),
                target_user_discord_id=target_discord_id,
                event_date=None,
                outcome=Outcome.FAILURE,
                error_message=f"Date generation failed: {str(e)}",
                recurring_pattern_id=None,
            )
            return

        # Check for no valid dates
        if not dates:
            await interaction.response.send_message(
                "❌ No valid dates generated from pattern. Please check your pattern description.",
                ephemeral=True,
            )
            self._create_audit_entry(
                action_type=ActionType.VOLUNTEER_RECURRING,
                user_discord_id=str(interaction.user.id),
                target_user_discord_id=target_discord_id,
                event_date=None,
                outcome=Outcome.FAILURE,
                error_message="No valid dates generated",
                recurring_pattern_id=None,
            )
            return

        # Check for conflicts (dates already assigned)
        conflicts = []
        valid_dates = []
        for event_date in dates:
            date_str = event_date.isoformat()
            existing_event = self.cache.get("events", date_str)
            if existing_event and existing_event.get("host_discord_id"):
                conflicts.append(event_date)
            else:
                valid_dates.append(event_date)

        # Check if all dates are conflicted
        if not valid_dates:
            conflict_list = "\n".join([f"- {format_date_pst(d)}" for d in conflicts[:5]])
            if len(conflicts) > 5:
                conflict_list += f"\n... and {len(conflicts) - 5} more"

            await interaction.response.send_message(
                f"❌ All dates generated from this pattern are already assigned:\n"
                f"{conflict_list}\n\n"
                f"Please choose a different pattern or contact an organizer.",
                ephemeral=True,
            )
            self._create_audit_entry(
                action_type=ActionType.VOLUNTEER_RECURRING,
                user_discord_id=str(interaction.user.id),
                target_user_discord_id=target_discord_id,
                event_date=None,
                outcome=Outcome.FAILURE,
                error_message="All dates conflicted",
                recurring_pattern_id=None,
            )
            return

        # Create preview embed
        embed = discord.Embed(
            title="📅 Recurring Pattern Preview",
            description=f"Pattern: **{pattern}**\nUser: <@{target_discord_id}>",
            color=discord.Color.blue(),
        )

        # Show valid dates
        valid_list = "\n".join([f"✅ {format_date_pst(d)}" for d in valid_dates[:10]])
        if len(valid_dates) > 10:
            valid_list += f"\n... and {len(valid_dates) - 10} more dates"
        embed.add_field(
            name=f"✅ Available Dates ({len(valid_dates)} total)",
            value=valid_list or "None",
            inline=False,
        )

        # Show conflicts if any
        if conflicts:
            conflict_list = "\n".join(
                [f"⚠️ {format_date_pst(d)} (already assigned)" for d in conflicts[:5]]
            )
            if len(conflicts) > 5:
                conflict_list += f"\n... and {len(conflicts) - 5} more"
            embed.add_field(
                name=f"⚠️ Conflicted Dates ({len(conflicts)} total)",
                value=conflict_list,
                inline=False,
            )

        embed.set_footer(
            text=f"Only {len(valid_dates)} date(s) will be assigned. "
            f"{len(conflicts)} conflicted date(s) will be skipped."
        )

        # Create confirmation view
        view = ConfirmationView(
            handler=self,
            interaction=interaction,
            target_user=target_user,
            pattern_description=pattern,
            pattern_dict=pattern_dict,
            dates=dates,
            conflicts=conflicts,
            valid_dates=valid_dates,
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _execute_recurring_assignment(
        self,
        interaction: discord.Interaction,
        target_user: discord.Member,
        pattern_description: str,
        pattern_dict: dict,
        valid_dates: list[date],
        conflicts: list[date],
        assigned_by_id: str,
    ) -> None:
        """
        Execute recurring pattern assignment after confirmation.

        Args:
            interaction: Discord interaction (from confirmation button)
            target_user: Target user to assign
            pattern_description: Human-readable pattern description
            pattern_dict: Parsed pattern dictionary
            valid_dates: List of valid (non-conflicted) dates
            conflicts: List of conflicted dates
            assigned_by_id: Discord ID of user who made the assignment
        """
        try:
            # Generate pattern ID
            pattern_id = str(uuid.uuid4())

            # Create pattern rule JSON
            pattern_rule_json = pattern_rule_to_json(pattern_dict)

            # Create RecurringPattern in Sheets
            now = datetime.now()
            pattern_row_data = [
                pattern_id,  # pattern_id
                str(target_user.id),  # host_discord_id
                str(target_user),  # host_username
                pattern_description,  # pattern_description
                pattern_rule_json,  # pattern_rule
                valid_dates[0].isoformat()
                if valid_dates
                else date.today().isoformat(),  # start_date
                "",  # end_date (nullable, indefinite)
                now.isoformat(),  # created_at
                "TRUE",  # is_active
            ]

            self.sheets.append_row(self.sheets.SHEET_RECURRING_PATTERNS, pattern_row_data)
            self.cache.increment_quota("writes", 1)

            # Batch assign all valid dates
            if valid_dates:
                await self._batch_assign_dates(
                    dates=valid_dates,
                    target_user=target_user,
                    assigned_by=assigned_by_id,
                    pattern_id=pattern_id,
                )

            # Create audit entry
            self._create_audit_entry(
                action_type=ActionType.VOLUNTEER_RECURRING,
                user_discord_id=assigned_by_id,
                target_user_discord_id=str(target_user.id),
                event_date=None,
                outcome=Outcome.SUCCESS,
                error_message=None,
                recurring_pattern_id=pattern_id,
            )

            # Update cache with pattern
            self.cache.set(
                "recurring_patterns",
                pattern_id,
                {
                    "host_discord_id": str(target_user.id),
                    "host_username": str(target_user),
                    "pattern_description": pattern_description,
                    "pattern_rule": pattern_rule_json,
                    "start_date": valid_dates[0].isoformat()
                    if valid_dates
                    else date.today().isoformat(),
                    "end_date": None,
                    "created_at": now.isoformat(),
                    "is_active": True,
                },
            )

            # Send success message
            success_msg = (
                f"✅ Successfully created recurring pattern: **{pattern_description}**\n\n"
                f"**Assigned {len(valid_dates)} date(s):**\n"
            )
            date_list = "\n".join([f"- {format_date_pst(d)}" for d in valid_dates[:10]])
            if len(valid_dates) > 10:
                date_list += f"\n... and {len(valid_dates) - 10} more"
            success_msg += date_list

            if conflicts:
                skipped_msg = f"\n\n⚠️ Skipped {len(conflicts)} conflicted date(s) "
                skipped_msg += "that were already assigned."
                success_msg += skipped_msg

            await interaction.followup.send(success_msg, ephemeral=True)

            self.logger.info(
                f"User {assigned_by_id} created recurring pattern {pattern_id} "
                f"for {target_user.id} with {len(valid_dates)} dates"
            )

        except Exception as e:
            self.logger.error(f"Failed to execute recurring assignment: {e}", exc_info=True)
            raise

    async def _batch_assign_dates(
        self,
        dates: list[date],
        target_user: discord.Member,
        assigned_by: str,
        pattern_id: str,
    ) -> None:
        """
        Batch assign multiple dates to a host.

        Args:
            dates: List of dates to assign
            target_user: Discord member to assign
            assigned_by: Discord ID of user making assignment
            pattern_id: Recurring pattern ID
        """
        now = datetime.now()

        # Prepare batch updates for Google Sheets
        updates = []
        rows_to_append = []

        for event_date in dates:
            date_str = event_date.isoformat()

            # Check if row already exists
            existing_row = self.sheets.find_row(self.sheets.SHEET_SCHEDULE, 1, date_str)

            row_data = [
                date_str,  # date
                str(target_user.id),  # host_discord_id
                str(target_user),  # host_username
                pattern_id,  # recurring_pattern_id
                now.isoformat(),  # assigned_at
                assigned_by,  # assigned_by
                "",  # notes
            ]

            if existing_row:
                # Update existing row (shouldn't happen for valid dates, but handle it)
                updates.append(
                    {
                        "range": f"A{existing_row}:G{existing_row}",
                        "values": [row_data],
                    }
                )
            else:
                # Append new row
                rows_to_append.append(row_data)

            # Update cache
            self.cache.set(
                "events",
                date_str,
                {
                    "host_discord_id": str(target_user.id),
                    "host_username": str(target_user),
                    "recurring_pattern_id": pattern_id,
                    "assigned_at": now.isoformat(),
                    "assigned_by": assigned_by,
                    "notes": None,
                },
            )

        # Batch update existing rows
        if updates:
            # Use batch_update for multiple ranges
            for update in updates:
                self.sheets.update_range(
                    self.sheets.SHEET_SCHEDULE, update["range"], update["values"]
                )
            self.cache.increment_quota("writes", len(updates))

        # Batch append new rows (gspread doesn't have batch append, so append one by one)
        # But we can optimize by doing them in sequence
        for row_data in rows_to_append:
            self.sheets.append_row(self.sheets.SHEET_SCHEDULE, row_data)
            self.cache.increment_quota("writes", 1)

        self.logger.info(
            f"Batch assigned {len(dates)} dates to {target_user.id} "
            f"({len(updates)} updated, {len(rows_to_append)} appended)"
        )

    async def _assign_host_to_date(
        self,
        date_str: str,
        validated_date,
        target_user: discord.Member,
        assigned_by: str,
    ) -> None:
        """
        Assign host to date in Google Sheets and cache.

        Args:
            date_str: Date string (YYYY-MM-DD)
            validated_date: Validated date object
            target_user: Discord member to assign
            assigned_by: Discord ID of user making assignment
        """
        now = datetime.now()

        # Prepare row data
        row_data = [
            date_str,  # date
            str(target_user.id),  # host_discord_id
            str(target_user),  # host_username
            "",  # recurring_pattern_id
            now.isoformat(),  # assigned_at
            assigned_by,  # assigned_by
            "",  # notes
        ]

        # Check if row already exists in Google Sheets
        existing_row = self.sheets.find_row(self.sheets.SHEET_SCHEDULE, 1, date_str)

        if existing_row:
            # Update existing row
            self.sheets.update_range(
                self.sheets.SHEET_SCHEDULE, f"A{existing_row}:G{existing_row}", [row_data]
            )
        else:
            # Append new row
            self.sheets.append_row(self.sheets.SHEET_SCHEDULE, row_data)

        # Increment quota
        self.cache.increment_quota("writes", 1)

        # Update cache
        self.cache.set(
            "events",
            date_str,
            {
                "host_discord_id": str(target_user.id),
                "host_username": str(target_user),
                "recurring_pattern_id": None,
                "assigned_at": now.isoformat(),
                "assigned_by": assigned_by,
                "notes": None,
            },
        )

        self.logger.info(f"Assigned {target_user.id} to {date_str} in Sheets and cache")

    def _create_audit_entry(
        self,
        action_type: ActionType,
        user_discord_id: str,
        target_user_discord_id: str,
        event_date,
        outcome: Outcome,
        error_message: Optional[str],
        recurring_pattern_id: Optional[str] = None,
    ) -> None:
        """
        Create audit log entry in Google Sheets.

        Args:
            action_type: Type of action
            user_discord_id: Discord ID of user performing action
            target_user_discord_id: Discord ID of affected user
            event_date: Date affected by action
            outcome: Success or failure
            error_message: Error message if failed
            recurring_pattern_id: Recurring pattern ID if applicable
        """
        try:
            entry_id = str(uuid.uuid4())
            now = datetime.now()

            row_data = [
                entry_id,
                now.isoformat(),
                action_type.value,
                user_discord_id,
                target_user_discord_id,
                event_date.isoformat() if event_date else "",
                recurring_pattern_id or "",  # recurring_pattern_id
                outcome.value,
                error_message or "",
                "{}",  # metadata (empty JSON)
            ]

            self.sheets.append_row(self.sheets.SHEET_AUDIT_LOG, row_data)
            self.cache.increment_quota("writes", 1)

            self.logger.info(f"Created audit entry: {entry_id}")

        except Exception as e:
            self.logger.error(f"Failed to create audit entry: {e}", exc_info=True)


def register_volunteer_command(
    tree: app_commands.CommandTree,
    sheets_service: SheetsService,
    cache_service: CacheService,
    sync_service: SyncService,
    config: dict,
) -> None:
    """
    Register /volunteer command with Discord bot.

    Args:
        tree: Discord command tree
        sheets_service: Google Sheets service instance
        cache_service: Cache service instance
        sync_service: Sync service instance
        config: Configuration dictionary
    """
    handler = VolunteerCommand(sheets_service, cache_service, sync_service, config)

    # Create a group for volunteer commands
    volunteer_group = app_commands.Group(
        name="volunteer",
        description="Volunteer to host on specific dates or set up recurring patterns",
    )

    @volunteer_group.command(name="date", description="Volunteer to host on a specific date")
    @app_commands.describe(
        date="Date to volunteer for (YYYY-MM-DD format, e.g., 2025-11-11)",
        user="User to volunteer on behalf of (requires host-privileged role)",
    )
    async def volunteer_date_command(
        interaction: discord.Interaction,
        date: str,
        user: Optional[discord.Member] = None,
    ):
        """Volunteer to host on a specific date."""
        await handler.handle(interaction, date, user)

    @volunteer_group.command(name="recurring", description="Set up a recurring hosting pattern")
    @app_commands.describe(
        pattern='Pattern description (e.g., "every 2nd Tuesday", "monthly", "biweekly")',
        user="User to set up pattern for (requires host-privileged role)",
    )
    async def volunteer_recurring_command(
        interaction: discord.Interaction,
        pattern: str,
        user: Optional[discord.Member] = None,
    ):
        """Set up a recurring hosting pattern."""
        await handler.handle_recurring(interaction, pattern, user)

    # Register the group
    tree.add_command(volunteer_group)
