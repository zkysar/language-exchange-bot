"""Warnings command handler."""

import logging

import discord
from discord import app_commands

from src.services.warning_service import WarningService
from src.utils.auth import authorize_admin_command


class WarningsCommand:
    """Handler for /warnings command."""

    def __init__(
        self,
        warning_service: WarningService,
        config: dict,
    ):
        """
        Initialize warnings command handler.

        Args:
            warning_service: Warning service instance
            config: Configuration dictionary from cache
        """
        self.warning_service = warning_service
        self.config = config
        self.logger = logging.getLogger("discord_host_scheduler.commands.warnings")

    def _get_config_int(self, key: str, default: int) -> int:
        """Return integer config value.

        Falls back to the provided default when parsing fails.
        """
        raw_value = self.config.get(key, default)
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            self.logger.debug(
                "Invalid %s value %r in config, defaulting to %s",
                key,
                raw_value,
                default,
            )
            return default

    async def handle(self, interaction: discord.Interaction) -> None:
        """
        Handle /warnings command.

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
            await interaction.response.send_message(
                f"❌ {str(e)}",
                ephemeral=True,
            )
            self.logger.warning(
                "User %s attempted to use /warnings without authorization",
                interaction.user.id,
            )
            return

        # Acknowledge interaction (can take up to 3 seconds)
        await interaction.response.defer(ephemeral=True)

        try:
            # Check for warnings
            self.logger.info("User %s triggered manual warning check", interaction.user.id)
            warnings = self.warning_service.check_warnings()

            if not warnings:
                # No warnings to post
                embed = discord.Embed(
                    title="✅ Warning Check Complete",
                    description=("No unassigned dates need warnings at this time."),
                    color=discord.Color.green(),
                )
                await interaction.followup.send(
                    embed=embed,
                    ephemeral=True,
                )
                self.logger.info("Warning check completed: no warnings found")
                return

            # Post warnings
            posted_count = await self.warning_service.post_warnings(warnings)

            # Build response embed
            urgent_count = sum(1 for warning in warnings if warning.severity.value == "urgent")
            passive_count = sum(1 for warning in warnings if warning.severity.value == "passive")
            warning_passive_days = self._get_config_int(
                "warning_passive_days",
                7,
            )
            warning_urgent_days = self._get_config_int(
                "warning_urgent_days",
                3,
            )
            passive_day_word = "day" if warning_passive_days == 1 else "days"
            urgent_day_word = "day" if warning_urgent_days == 1 else "days"

            embed = discord.Embed(
                title="⚠️ Warning Check Complete",
                description=(f"Posted {posted_count} warning(s) " "to the configured channel."),
                color=discord.Color.orange(),
            )

            embed.add_field(
                name="Warnings Found",
                value=(
                    f"🚨 Urgent: {urgent_count}\n"
                    f"⚠️ Passive: {passive_count}\n"
                    f"**Total: {len(warnings)}**"
                ),
                inline=False,
            )

            urgent_definition = (
                "🚨 Urgent: Host needed within "
                f"{warning_urgent_days} {urgent_day_word} "
                "(organizer ping)."
            )
            passive_definition = (
                "⚠️ Passive: Host needed within "
                f"{warning_passive_days} {passive_day_word}; "
                "escalates to urgent once "
                f"{warning_urgent_days} {urgent_day_word} remain."
            )

            embed.add_field(
                name="What the severities mean",
                value=f"{urgent_definition}\n{passive_definition}",
                inline=False,
            )

            # Check if channel is configured
            warnings_channel_id = self.config.get("warnings_channel_id")
            if warnings_channel_id:
                try:
                    channel = self.warning_service.client.get_channel(int(warnings_channel_id))
                    if channel:
                        embed.add_field(
                            name="Channel",
                            value=f"Posted to: {channel.mention}",
                            inline=False,
                        )
                except (ValueError, TypeError):
                    pass

            await interaction.followup.send(embed=embed, ephemeral=True)
            self.logger.info("Warning check completed: %s warnings posted", posted_count)

        except Exception as e:
            error_msg = f"❌ Warning check failed: {str(e)}"
            self.logger.error(
                "Error during warning check: %s",
                e,
                exc_info=True,
            )

            embed = discord.Embed(
                title="❌ Warning Check Failed",
                description=error_msg,
                color=discord.Color.red(),
            )

            # Check if channel is configured
            warnings_channel_id = self.config.get("warnings_channel_id")
            if not warnings_channel_id:
                embed.add_field(
                    name="⚠️ Configuration Error",
                    value=(
                        "warnings_channel_id is not configured. "
                        "Configure it in the Configuration sheet."
                    ),
                    inline=False,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)


def register_warnings_command(
    tree: app_commands.CommandTree,
    warning_service: WarningService,
    config: dict,
) -> None:
    """
    Register /warnings command with Discord bot.

    Args:
        tree: Discord command tree
        warning_service: Warning service instance
        config: Configuration dictionary
    """
    handler = WarningsCommand(warning_service, config)

    @tree.command(
        name="warnings",
        description=("Check and post warnings about unassigned dates " "(admin only)"),
    )
    async def warnings_command(interaction: discord.Interaction):
        """Check and post warnings about unassigned dates."""
        await handler.handle(interaction)
