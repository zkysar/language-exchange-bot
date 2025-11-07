"""Discord bot service foundation."""

import logging
from typing import Optional

import discord
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
