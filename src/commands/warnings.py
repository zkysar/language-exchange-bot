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
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
            self.logger.warning(
                f"User {interaction.user.id} attempted to use /warnings without authorization"
            )
            return

        # Acknowledge interaction (can take up to 3 seconds)
        await interaction.response.defer(ephemeral=True)

        try:
            # Check for warnings
            self.logger.info(f"User {interaction.user.id} triggered manual warning check")
            warnings = self.warning_service.check_warnings()

            if not warnings:
                # No warnings to post
                embed = discord.Embed(
                    title="✅ Warning Check Complete",
                    description="No unassigned dates need warnings at this time.",
                    color=discord.Color.green(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                self.logger.info("Warning check completed: no warnings found")
                return

            # Post warnings
            posted_count = await self.warning_service.post_warnings(warnings)

            # Build response embed
            urgent_count = sum(1 for w in warnings if w.severity.value == "urgent")
            passive_count = sum(1 for w in warnings if w.severity.value == "passive")

            embed = discord.Embed(
                title="⚠️ Warning Check Complete",
                description=f"Posted {posted_count} warning(s) to the configured channel.",
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
            self.logger.info(f"Warning check completed: {posted_count} warnings posted")

        except Exception as e:
            error_msg = f"❌ Warning check failed: {str(e)}"
            self.logger.error(f"Error during warning check: {e}", exc_info=True)

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
                        "Please configure it in the Configuration sheet."
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
        name="warnings", description="Check and post warnings about unassigned dates (admin only)"
    )
    async def warnings_command(interaction: discord.Interaction):
        """Check and post warnings about unassigned dates."""
        await handler.handle(interaction)
