"""Main bot entry point."""

import asyncio
import os
import signal
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from src.services.cache_service import CacheService
from src.services.discord_service import DiscordService
from src.services.sheets_service import SheetsService
from src.services.sync_service import SyncService
from src.services.warning_service import WarningService
from src.utils.logger import setup_logging


class DiscordHostSchedulerBot:
    """
    Discord Host Scheduler Bot main application.

    Coordinates all services and handles bot lifecycle.
    """

    def __init__(self):
        """Initialize bot and services."""
        # Load environment variables
        load_dotenv()

        # Set up logging
        self.logger = setup_logging()
        self.logger.info("Initializing Discord Host Scheduler Bot")

        # Validate environment variables
        self._validate_env()

        # Initialize services
        self._init_services()

        # Event loop reference for signal handlers
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _validate_env(self) -> None:
        """
        Validate required environment variables.

        Raises:
            ValueError: If required environment variables are missing
        """
        required_vars = [
            "DISCORD_BOT_TOKEN",
            "GOOGLE_SHEETS_SPREADSHEET_ID",
            "GOOGLE_SHEETS_CREDENTIALS_FILE",
        ]

        missing = [var for var in required_vars if not os.getenv(var)]

        if missing:
            error_msg = f"Missing required environment variables: {', '.join(missing)}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        # Validate credentials file exists
        creds_file = os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE")
        if not Path(creds_file).exists():
            error_msg = f"Google Sheets credentials file not found: {creds_file}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)

    def _init_services(self) -> None:
        """Initialize all bot services."""
        # Cache service
        cache_ttl = int(os.getenv("CACHE_TTL_SECONDS", "300"))
        self.cache_service = CacheService(cache_file="cache.json", ttl_seconds=cache_ttl)
        self.logger.info("Cache service initialized")

        # Google Sheets service
        self.sheets_service = SheetsService(
            spreadsheet_id=os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID"),
            credentials_file=os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE"),
        )
        self.logger.info("Google Sheets service initialized")

        # Sync service (will update TTL from config after startup sync)
        self.sync_service = SyncService(
            self.sheets_service, self.cache_service, ttl_seconds=cache_ttl
        )
        self.logger.info("Sync service initialized")

        # Discord service
        self.discord_service = DiscordService(token=os.getenv("DISCORD_BOT_TOKEN"))
        self.logger.info("Discord service initialized")

        # Warning service (depends on Discord service client)
        # Will be initialized after Discord client is ready
        self.warning_service: Optional[WarningService] = None

    def _register_commands(self) -> None:
        """Register Discord slash commands."""
        from src.commands import (
            register_help_command,
            register_listdates_command,
            register_reset_command,
            register_schedule_command,
            register_sync_command,
            register_unvolunteer_command,
            register_volunteer_command,
            register_warnings_command,
        )

        # Get configuration from cache
        config = self._get_config_dict()

        # Initialize warning service (requires Discord client)
        if self.warning_service is None:
            self.warning_service = WarningService(
                self.sheets_service,
                self.cache_service,
                self.discord_service.client,
                config,
            )
            self.logger.info("Warning service initialized")

        # Register /help command
        register_help_command(
            self.discord_service.tree,
            self.sheets_service,
            self.cache_service,
            self.sync_service,
            config,
        )

        # Register /volunteer command
        register_volunteer_command(
            self.discord_service.tree,
            self.sheets_service,
            self.cache_service,
            self.sync_service,
            config,
        )

        # Register /listdates command
        register_listdates_command(
            self.discord_service.tree,
            self.sheets_service,
            self.cache_service,
            self.sync_service,
            config,
        )

        # Register /unvolunteer command (with warning service for immediate checks)
        register_unvolunteer_command(
            self.discord_service.tree,
            self.sheets_service,
            self.cache_service,
            self.sync_service,
            config,
            warning_service=self.warning_service,
        )

        # Register /schedule command
        register_schedule_command(
            self.discord_service.tree,
            self.sheets_service,
            self.cache_service,
            self.sync_service,
            config,
        )

        # Register /sync command
        register_sync_command(
            self.discord_service.tree,
            self.sheets_service,
            self.cache_service,
            self.sync_service,
            config,
        )

        # Register /warnings command
        register_warnings_command(
            self.discord_service.tree,
            self.warning_service,
            config,
        )

        # Register /reset command
        register_reset_command(
            self.discord_service.tree,
            self.sheets_service,
            self.cache_service,
            self.sync_service,
            config,
        )

        self.logger.info("Commands registered")

    def _get_config_dict(self) -> dict:
        """
        Get configuration as dictionary from cache.

        Returns:
            Dictionary with configuration values
        """
        config_data = self.cache_service.get("configuration") or {}

        # Parse configuration values
        config = {}
        for key, value_dict in config_data.items():
            if isinstance(value_dict, dict):
                # Parse typed value
                from src.models import Configuration, SettingType

                try:
                    cfg = Configuration(
                        setting_key=key,
                        setting_value=value_dict.get("setting_value", ""),
                        setting_type=SettingType(value_dict.get("setting_type", "string")),
                    )
                    config[key] = cfg.get_typed_value()
                except Exception as e:
                    self.logger.warning(f"Failed to parse config {key}: {e}")
                    config[key] = value_dict.get("setting_value")
            else:
                config[key] = value_dict

        return config

    async def startup_sync(self) -> None:
        """Perform initial sync on bot startup."""
        self.logger.info("Performing startup sync")
        try:
            stats = self.sync_service.sync_all(detect_conflicts=False)
            self.logger.info(f"Startup sync completed: {stats}")

            # Update sync service TTL from configuration if available
            config = self._get_config_dict()
            cache_ttl = config.get("cache_ttl_seconds", 300)
            if isinstance(cache_ttl, int) and cache_ttl > 0:
                self.sync_service.ttl_seconds = cache_ttl
                self.cache_service.ttl_seconds = cache_ttl
                self.logger.info(f"Updated cache TTL to {cache_ttl} seconds from configuration")

        except Exception as e:
            self.logger.error(f"Startup sync failed: {e}")
            self.logger.warning("Bot will start with stale/empty cache")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, shutting down gracefully")
        if self._loop and self._loop.is_running():
            # Schedule shutdown task on the running event loop
            self._loop.create_task(self.shutdown())
        else:
            self.logger.warning("Event loop not available, forcing exit")
            sys.exit(0)

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        self.logger.info("Shutting down bot")

        # Stop periodic sync task
        if self.sync_service:
            await self.sync_service.stop_periodic_sync()

        # Stop daily warning check task
        if self.discord_service:
            await self.discord_service.stop_daily_warning_check()

        # Close Discord connection
        if self.discord_service:
            await self.discord_service.close()

        self.logger.info("Bot shutdown complete")
        sys.exit(0)

    async def run(self) -> None:
        """Run the bot."""
        try:
            # Store event loop reference for signal handlers
            self._loop = asyncio.get_running_loop()

            # Perform startup sync
            await self.startup_sync()

            # Register commands (warning service will be initialized here)
            self._register_commands()

            # Start periodic sync task
            await self.sync_service.start_periodic_sync()
            self.logger.info("Periodic sync task started")

            # Start daily warning check task
            if self.warning_service:
                config = self._get_config_dict()
                daily_check_time = config.get("daily_check_time", "09:00")
                # Remove "PST" suffix if present
                if isinstance(daily_check_time, str):
                    daily_check_time = (
                        daily_check_time.replace(" PST", "").replace(" PDT", "").strip()
                    )
                self.discord_service.start_daily_warning_check(
                    self.warning_service,
                    check_time=daily_check_time,
                )
                self.logger.info("Daily warning check task started")

            # Start Discord bot
            self.logger.info("Starting Discord bot")
            await self.discord_service.start()

        except Exception as e:
            self.logger.error(f"Bot crashed: {e}", exc_info=True)
            sys.exit(1)


def main():
    """Main entry point."""
    bot = DiscordHostSchedulerBot()
    asyncio.run(bot.run())


if __name__ == "__main__":
    main()
