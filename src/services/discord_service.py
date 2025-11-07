"""Discord bot service foundation."""

import asyncio
import logging
from datetime import datetime
from datetime import time as dt_time
from datetime import timedelta
from typing import Any, Optional

import discord
import pytz
from discord import app_commands


class DiscordService:
    """
    Discord bot service for command handling and event management.

    This is the foundation service that will be extended in user story phases.
    """

    def __init__(self, token: str, intents: Optional[discord.Intents] = None):
        """
        Initialize Discord service.

        Args:
            token: Discord bot token
            intents: Discord intents (defaults to default intents)
        """
        self.token = token
        self.logger = logging.getLogger("discord_host_scheduler.discord")

        # Set up intents
        if intents is None:
            intents = discord.Intents.default()
            intents.message_content = True
            intents.members = True

        # Create bot client
        self.client = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.client)

        # Daily warning check task
        self._daily_warning_task: Optional[asyncio.Task] = None
        self._warning_service: Optional[Any] = None
        self._stop_daily_warning = False

        # Register event handlers
        self._register_events()

    def _register_events(self) -> None:
        """Register Discord event handlers."""

        @self.client.event
        async def on_ready():
            """Handle bot ready event."""
            self.logger.info(f"Bot connected as {self.client.user}")
            self.logger.info(f"Bot ID: {self.client.user.id}")
            self.logger.info(f"Connected to {len(self.client.guilds)} guilds")

            # Sync slash commands
            try:
                synced = await self.tree.sync()
                self.logger.info(f"Synced {len(synced)} command(s)")
            except Exception as e:
                self.logger.error(f"Failed to sync commands: {e}")

        @self.client.event
        async def on_error(event, *args, **kwargs):
            """Handle Discord errors."""
            self.logger.error(f"Discord error in {event}", exc_info=True)

    def register_command(
        self,
        name: str,
        description: str,
        callback,
        parameters: Optional[list] = None,
    ) -> None:
        """
        Register a slash command.

        Args:
            name: Command name
            description: Command description
            callback: Async function to call when command is invoked
            parameters: List of app_commands parameters (optional)
        """

        @self.tree.command(name=name, description=description)
        async def command_wrapper(interaction: discord.Interaction, **kwargs):
            """Wrapper for command callback."""
            try:
                await callback(interaction, **kwargs)
            except Exception as e:
                self.logger.error(f"Error in command /{name}: {e}", exc_info=True)
                await interaction.response.send_message(
                    f"❌ An error occurred: {str(e)}", ephemeral=True
                )

        self.logger.info(f"Registered command: /{name}")

    async def start(self) -> None:
        """Start the Discord bot."""
        self.logger.info("Starting Discord bot")
        await self.client.start(self.token)

    async def close(self) -> None:
        """Close the Discord bot connection."""
        self.logger.info("Closing Discord bot")
        await self.client.close()

    def run(self) -> None:
        """
        Run the Discord bot (blocking).

        Note: This is a blocking call. Use start() for async contexts.
        """
        self.logger.info("Running Discord bot (blocking)")
        self.client.run(self.token)

    def start_daily_warning_check(
        self,
        warning_service: Any,
        check_time: str = "09:00",
    ) -> None:
        """
        Start daily warning check task.

        Args:
            warning_service: WarningService instance
            check_time: Time of day for daily check in HH:MM format (PST, default: 09:00)
        """
        if self._daily_warning_task and not self._daily_warning_task.done():
            self.logger.warning("Daily warning check task already running")
            return

        self._warning_service = warning_service
        self._stop_daily_warning = False

        async def _daily_warning_loop():
            """Daily warning check loop."""
            # Wait for bot to be ready
            await self.client.wait_until_ready()

            pst = pytz.timezone("America/Los_Angeles")

            # Parse check time
            try:
                hour, minute = map(int, check_time.split(":"))
                check_time_obj = dt_time(hour, minute)
            except (ValueError, AttributeError):
                self.logger.warning(f"Invalid check_time format: {check_time}, using default 09:00")
                check_time_obj = dt_time(9, 0)

            while not self._stop_daily_warning:
                try:
                    # Get current time in PST
                    now_pst = datetime.now(pst)
                    current_time = now_pst.time()

                    # Calculate next check time
                    next_check = datetime.combine(now_pst.date(), check_time_obj, pst)
                    if current_time >= check_time_obj:
                        # If check time has passed today, schedule for tomorrow
                        next_check += timedelta(days=1)

                    # Wait until check time
                    wait_seconds = (next_check - now_pst).total_seconds()
                    if wait_seconds > 0:
                        next_check_str = next_check.strftime("%Y-%m-%d %H:%M:%S %Z")
                        self.logger.info(
                            "Next warning check scheduled for %s",
                            next_check_str,
                        )
                        await asyncio.sleep(wait_seconds)

                    if self._stop_daily_warning:
                        break

                    # Perform warning check
                    self.logger.info("Running daily warning check")
                    try:
                        posted_count = await warning_service.check_and_post_warnings()
                        self.logger.info(
                            f"Daily warning check completed: {posted_count} warnings posted"
                        )
                    except Exception as e:
                        self.logger.error(f"Error in daily warning check: {e}", exc_info=True)

                    # Wait a bit before recalculating next check time
                    await asyncio.sleep(60)

                except asyncio.CancelledError:
                    self.logger.info("Daily warning check task cancelled")
                    break
                except Exception as e:
                    self.logger.error(f"Error in daily warning check loop: {e}", exc_info=True)
                    # Wait a bit before retrying to avoid tight error loops
                    await asyncio.sleep(300)  # 5 minutes

        self._daily_warning_task = asyncio.create_task(_daily_warning_loop())
        self.logger.info(f"Started daily warning check task (check time: {check_time} PST)")

    async def stop_daily_warning_check(self) -> None:
        """Stop daily warning check task."""
        self._stop_daily_warning = True
        if self._daily_warning_task and not self._daily_warning_task.done():
            self._daily_warning_task.cancel()
            try:
                await self._daily_warning_task
            except asyncio.CancelledError:
                pass
            self.logger.info("Stopped daily warning check task")
