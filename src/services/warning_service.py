"""Warning service for generating and posting warnings about unassigned dates."""

import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

import discord

from src.models import ActionType, Outcome, Warning, WarningSeverity
from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService
from src.utils.date_parser import get_current_date_pst


class WarningService:
    """
    Service for generating and posting warnings about unassigned dates.

    Checks for unassigned dates, calculates severity, and posts warnings to Discord.
    """

    def __init__(
        self,
        sheets_service: SheetsService,
        cache_service: CacheService,
        discord_client: discord.Client,
        config: dict,
    ):
        """
        Initialize warning service.

        Args:
            sheets_service: Google Sheets service instance
            cache_service: Cache service instance
            discord_client: Discord client instance for posting messages
            config: Configuration dictionary from cache
        """
        self.sheets = sheets_service
        self.cache = cache_service
        self.client = discord_client
        self.config = config
        self.logger = logging.getLogger("discord_host_scheduler.warning")

    def check_warnings(self) -> list[Warning]:
        """
        Check for unassigned dates and generate warnings.

        Returns:
            List of Warning objects for unassigned dates that need warnings
        """
        warnings: list[Warning] = []

        try:
            # Get configuration values
            warning_passive_days_raw = self.config.get("warning_passive_days", 7)
            warning_urgent_days_raw = self.config.get("warning_urgent_days", 3)

            try:
                warning_passive_days = int(warning_passive_days_raw)
            except (TypeError, ValueError):
                self.logger.warning(
                    "Invalid warning_passive_days value %r, defaulting to 7",
                    warning_passive_days_raw,
                )
                warning_passive_days = 7

            try:
                warning_urgent_days = int(warning_urgent_days_raw)
            except (TypeError, ValueError):
                self.logger.warning(
                    "Invalid warning_urgent_days value %r, defaulting to 3",
                    warning_urgent_days_raw,
                )
                warning_urgent_days = 3

            max_warning_window = max(warning_passive_days, warning_urgent_days)

            # Get all events from cache
            events = self.cache.get("events") or {}
            today = get_current_date_pst()

            evaluated_dates: set[date] = set()

            # Evaluate upcoming dates within warning window
            for offset in range(max_warning_window + 1):
                event_date = today + timedelta(days=offset)
                evaluated_dates.add(event_date)

                warning = self._evaluate_date_for_warning(
                    events,
                    event_date,
                    today,
                    warning_passive_days,
                    warning_urgent_days,
                )
                if warning:
                    warnings.append(warning)

            # Evaluate cached dates that may not be contiguous in range
            for date_str, event_data in events.items():
                try:
                    event_date = date.fromisoformat(date_str)
                except (ValueError, TypeError):
                    self.logger.warning(f"Invalid date format in cache: {date_str}")
                    continue

                if event_date in evaluated_dates:
                    continue

                days_until_event = (event_date - today).days
                if days_until_event < 0 or days_until_event > max_warning_window:
                    continue

                warning = self._evaluate_date_for_warning(
                    {date_str: event_data},
                    event_date,
                    today,
                    warning_passive_days,
                    warning_urgent_days,
                )
                if warning:
                    warnings.append(warning)

        except Exception as e:
            self.logger.error(f"Error checking warnings: {e}", exc_info=True)

        return warnings

    async def post_warnings(self, warnings: list[Warning]) -> int:
        """
        Post warnings to Discord channel.

        Args:
            warnings: List of Warning objects to post

        Returns:
            Number of warnings successfully posted
        """
        if not warnings:
            return 0

        posted_count = 0

        try:
            # Get warnings channel ID from config
            warnings_channel_id = self.config.get("warnings_channel_id")
            if not warnings_channel_id:
                self.logger.warning("warnings_channel_id not configured, cannot post warnings")
                return 0

            # Get channel
            try:
                channel = self.client.get_channel(int(warnings_channel_id))
                if not channel or not isinstance(channel, discord.TextChannel):
                    self.logger.error(f"Invalid warnings channel ID: {warnings_channel_id}")
                    return 0
            except (ValueError, TypeError) as e:
                self.logger.error(f"Invalid warnings_channel_id format: {e}")
                return 0

            # Get organizer role IDs for pinging
            organizer_role_ids = self.config.get("organizer_role_ids", [])
            if not isinstance(organizer_role_ids, list):
                organizer_role_ids = []

            # Separate warnings by severity
            urgent_warnings = [w for w in warnings if w.severity == WarningSeverity.URGENT]
            passive_warnings = [w for w in warnings if w.severity == WarningSeverity.PASSIVE]

            # Post urgent warnings first (with ping)
            if urgent_warnings:
                await self._post_urgent_warnings(channel, urgent_warnings, organizer_role_ids)
                posted_count += len(urgent_warnings)

                # Update warning status
                for warning in urgent_warnings:
                    warning.posted_at = datetime.now()
                    warning.posted_channel_id = str(channel.id)

            # Post passive warnings
            if passive_warnings:
                await self._post_passive_warnings(channel, passive_warnings)
                posted_count += len(passive_warnings)

                # Update warning status
                for warning in passive_warnings:
                    warning.posted_at = datetime.now()
                    warning.posted_channel_id = str(channel.id)

            # Create audit entries for posted warnings
            for warning in warnings:
                if warning.is_posted():
                    self._create_audit_entry(
                        action_type=ActionType.WARNING_POSTED,
                        user_discord_id="0",  # System action
                        event_date=warning.event_date,
                        outcome=Outcome.SUCCESS,
                        severity=warning.severity.value,
                        days_until_event=warning.days_until_event,
                    )

            self.logger.info(
                "Posted %s warnings (%s urgent, %s passive)",
                posted_count,
                len(urgent_warnings),
                len(passive_warnings),
            )

        except Exception as e:
            self.logger.error(f"Error posting warnings: {e}", exc_info=True)

        return posted_count

    async def _post_urgent_warnings(
        self,
        channel: discord.TextChannel,
        warnings: list[Warning],
        organizer_role_ids: list[str],
    ) -> None:
        """
        Post urgent warnings to Discord channel with organizer role ping.

        Args:
            channel: Discord channel to post to
            warnings: List of urgent Warning objects
            organizer_role_ids: List of organizer role IDs to ping
        """
        # Build role mentions for pinging
        role_mentions = []
        for role_id in organizer_role_ids:
            try:
                role = channel.guild.get_role(int(role_id))
                if role:
                    role_mentions.append(role.mention)
            except (ValueError, TypeError):
                continue

        # Build message with role ping
        if role_mentions:
            content = f"{' '.join(role_mentions)} **URGENT: Unassigned Dates Need Hosts!**"
        else:
            content = "**🚨 URGENT: Unassigned Dates Need Hosts!**"

        # Create embed
        embed = discord.Embed(
            title="🚨 Urgent Warning",
            description="These dates need hosts within 3 days!",
            color=discord.Color.red(),
            timestamp=datetime.now(),
        )

        # Add warning details
        warning_list = []
        for warning in warnings:
            date_str = warning.event_date.strftime("%Y-%m-%d")
            plural_suffix = "" if warning.days_until_event == 1 else "s"
            warning_list.append(
                f"**{date_str}** ({warning.days_until_event} day{plural_suffix} away)"
            )

        embed.add_field(
            name="Unassigned Dates",
            value="\n".join(warning_list) or "None",
            inline=False,
        )

        embed.set_footer(text=f"{len(warnings)} urgent warning(s)")

        await channel.send(content=content, embed=embed)

    async def _post_passive_warnings(
        self,
        channel: discord.TextChannel,
        warnings: list[Warning],
    ) -> None:
        """
        Post passive warnings to Discord channel.

        Args:
            channel: Discord channel to post to
            warnings: List of passive Warning objects
        """
        # Create embed
        embed = discord.Embed(
            title="⚠️ Passive Warning",
            description="These dates need hosts within 7 days.",
            color=discord.Color.orange(),
            timestamp=datetime.now(),
        )

        # Add warning details
        warning_list = []
        for warning in warnings:
            date_str = warning.event_date.strftime("%Y-%m-%d")
            plural_suffix = "" if warning.days_until_event == 1 else "s"
            warning_list.append(
                f"**{date_str}** ({warning.days_until_event} day{plural_suffix} away)"
            )

        embed.add_field(
            name="Unassigned Dates",
            value="\n".join(warning_list) or "None",
            inline=False,
        )

        embed.set_footer(text=f"{len(warnings)} passive warning(s)")

        await channel.send(embed=embed)

    async def check_and_post_warnings(self) -> int:
        """
        Check for warnings and post them to Discord.

        Returns:
            Number of warnings posted
        """
        warnings = self.check_warnings()
        if not warnings:
            self.logger.debug("No warnings to post")
            return 0

        return await self.post_warnings(warnings)

    def _create_audit_entry(
        self,
        action_type: ActionType,
        user_discord_id: str,
        event_date: date,
        outcome: Outcome,
        severity: Optional[str] = None,
        days_until_event: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Create audit log entry for warning action.

        Args:
            action_type: Type of action
            user_discord_id: Discord ID of user (0 for system actions)
            event_date: Date affected by action
            outcome: Success or failure
            severity: Warning severity (optional)
            days_until_event: Days until event (optional)
            error_message: Error message if failed (optional)
        """
        try:
            import json

            entry_id = str(uuid.uuid4())
            now = datetime.now()

            # Build metadata
            metadata = {}
            if severity:
                metadata["severity"] = severity
            if days_until_event is not None:
                metadata["days_until_event"] = days_until_event

            row_data = [
                entry_id,
                now.isoformat(),
                action_type.value,
                user_discord_id,
                "",  # target_user_discord_id (not applicable for warnings)
                event_date.isoformat(),
                "",  # recurring_pattern_id
                outcome.value,
                error_message or "",
                json.dumps(metadata),  # metadata
            ]

            self.sheets.append_row(self.sheets.SHEET_AUDIT_LOG, row_data)
            self.cache.increment_quota("writes", 1)

            self.logger.debug(f"Created audit entry for warning: {entry_id}")

        except Exception as e:
            self.logger.error(f"Failed to create audit entry: {e}", exc_info=True)

    def _evaluate_date_for_warning(
        self,
        events: dict[str, dict],
        event_date: date,
        today: date,
        warning_passive_days: int,
        warning_urgent_days: int,
    ) -> Optional[Warning]:
        """
        Determine whether a given date needs a warning.

        Args:
            events: Dictionary of cached events
            event_date: Date being evaluated
            today: Today's date in PST
            warning_passive_days: Passive warning threshold
            warning_urgent_days: Urgent warning threshold

        Returns:
            Warning instance if a warning is needed, otherwise None
        """
        date_key = event_date.isoformat()
        event_data = events.get(date_key)

        host_discord_id = None
        if event_data:
            host_discord_id = event_data.get("host_discord_id")
            if isinstance(host_discord_id, str):
                host_discord_id = host_discord_id.strip()

        if host_discord_id:
            return None

        days_until = (event_date - today).days
        if days_until < 0:
            return None

        if days_until <= warning_urgent_days:
            severity = WarningSeverity.URGENT
        elif days_until <= warning_passive_days:
            severity = WarningSeverity.PASSIVE
        else:
            return None

        return Warning(
            warning_id=str(uuid.uuid4()),
            event_date=event_date,
            severity=severity,
            days_until_event=days_until,
        )
