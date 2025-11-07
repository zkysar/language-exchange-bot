"""Help command handler."""

import logging
from typing import Optional

import discord
from discord import app_commands

from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService
from src.services.sync_service import SyncService


class HelpCommand:
    """Handler for /help command."""

    def __init__(
        self,
        sheets_service: SheetsService,
        cache_service: CacheService,
        sync_service: SyncService,
        config: dict,
    ):
        """
        Initialize help command handler.

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
        self.logger = logging.getLogger("discord_host_scheduler.commands.help")

        # Define all commands and their descriptions
        self.commands = {
            "volunteer": {
                "description": "Sign up to host on specific dates or set up recurring patterns",
                "subcommands": {
                    "date": {
                        "description": "Volunteer to host on a specific date",
                        "parameters": {
                            "date": "Date to volunteer for (YYYY-MM-DD format, e.g., 2025-11-11)",
                            "user": "User to volunteer on behalf of (requires host-privileged role) - optional",
                        },
                        "examples": [
                            "/volunteer date date:2025-11-11",
                            "/volunteer date date:2025-12-25 user:@username",
                        ],
                    },
                    "recurring": {
                        "description": "Set up a recurring hosting pattern",
                        "parameters": {
                            "pattern": 'Pattern description (e.g., "every 2nd Tuesday", "monthly", "biweekly")',
                            "user": "User to set up pattern for (requires host-privileged role) - optional",
                        },
                        "examples": [
                            '/volunteer recurring pattern:"every 2nd Tuesday"',
                            '/volunteer recurring pattern:"monthly" user:@username',
                        ],
                    },
                },
            },
            "unvolunteer": {
                "description": "Cancel your hosting commitment for a specific date",
                "parameters": {
                    "date": "Date to unvolunteer from (YYYY-MM-DD format, e.g., 2025-11-11)",
                    "user": "User to unvolunteer on behalf of (requires host-privileged role) - optional",
                },
                "examples": [
                    "/unvolunteer date:2025-11-11",
                    "/unvolunteer date:2025-12-25 user:@username",
                ],
                "note": "Note: Recurring pattern cancellation is coming soon.",
            },
            "schedule": {
                "description": "View upcoming host schedule",
                "parameters": {
                    "date": "View specific date (YYYY-MM-DD format) - optional",
                    "weeks": "Number of weeks to show (default: 8, max: 52) - optional",
                },
                "examples": [
                    "/schedule",
                    "/schedule date:2025-11-11",
                    "/schedule weeks:4",
                ],
            },
            "sync": {
                "description": "Force immediate synchronization with Google Sheets (admin only)",
                "parameters": {},
                "examples": ["/sync"],
                "permissions": "Requires organizer role",
            },
            "listdates": {
                "description": "View all your upcoming hosting dates (coming soon)",
                "parameters": {
                    "user": "User to list dates for (requires host-privileged role) - optional",
                },
                "examples": ["/listdates", "/listdates user:@username"],
                "status": "coming_soon",
            },
            "warnings": {
                "description": "Manually trigger warning check for unassigned dates (admin only, coming soon)",
                "parameters": {},
                "examples": ["/warnings"],
                "permissions": "Requires organizer role",
                "status": "coming_soon",
            },
            "reset": {
                "description": "Display instructions for safely resetting the database (admin only)",
                "parameters": {},
                "examples": ["/reset"],
                "permissions": "Requires organizer role",
            },
        }

    async def handle(
        self,
        interaction: discord.Interaction,
        command: Optional[str] = None,
        subcommand: Optional[str] = None,
    ) -> None:
        """
        Handle /help command.

        Args:
            interaction: Discord interaction
            command: Optional command name to get detailed help for
            subcommand: Optional subcommand name (for commands with subcommands)
        """
        if command:
            # Handle case where command might contain subcommand (e.g., "volunteer recurring")
            # Parse command if it contains a space
            if " " in command and not subcommand:
                parts = command.split(" ", 1)
                command = parts[0]
                subcommand = parts[1] if len(parts) > 1 else None

            # Show detailed help for specific command
            await self._show_detailed_help(interaction, command, subcommand)
        else:
            # Show list of all commands
            await self._show_command_list(interaction)

    async def _show_command_list(self, interaction: discord.Interaction) -> None:
        """
        Show list of all available commands.

        Args:
            interaction: Discord interaction
        """
        embed = discord.Embed(
            title="📚 Command Reference",
            description="Available commands for the Discord Host Scheduler Bot",
            color=discord.Color.blue(),
        )

        # User Commands section
        user_commands_text = ""
        user_commands_text += f"**/volunteer date** - Sign up to host on a specific date\n"
        user_commands_text += f"**/volunteer recurring** - Set up recurring hosting patterns\n"
        user_commands_text += f"**/unvolunteer** - Cancel your hosting commitment\n"
        user_commands_text += f"**/schedule** - View upcoming host schedule\n"
        user_commands_text += f"**/help** - Show this help message\n"
        user_commands_text += f"\n*Coming soon:*\n"
        user_commands_text += f"**/listdates** - View all your upcoming hosting dates\n"

        embed.add_field(name="👤 User Commands", value=user_commands_text, inline=False)

        # Administrative Commands section
        admin_commands_text = ""
        admin_commands_text += (
            f"**/sync** - Force synchronization with Google Sheets (admin only)\n"
        )
        admin_commands_text += f"**/reset** - Display database reset instructions (admin only)\n"
        admin_commands_text += f"\n*Coming soon:*\n"
        admin_commands_text += f"**/warnings** - Manually trigger warning check (admin only)\n"

        embed.add_field(name="⚙️ Administrative Commands", value=admin_commands_text, inline=False)

        embed.add_field(
            name="💡 Getting More Help",
            value="Use `/help [command]` to get detailed information about a specific command.\n"
            "Example: `/help volunteer` or `/help volunteer recurring`",
            inline=False,
        )

        embed.set_footer(text="All dates are displayed in PST timezone. Date format: YYYY-MM-DD")

        await interaction.response.send_message(embed=embed)

    async def _show_detailed_help(
        self,
        interaction: discord.Interaction,
        command: str,
        subcommand: Optional[str] = None,
    ) -> None:
        """
        Show detailed help for a specific command.

        Args:
            interaction: Discord interaction
            command: Command name
            subcommand: Optional subcommand name
        """
        command_lower = command.lower()

        # Handle subcommands (e.g., "volunteer recurring")
        if command_lower == "volunteer" and subcommand:
            subcommand_lower = subcommand.lower()
            if subcommand_lower in self.commands.get("volunteer", {}).get("subcommands", {}):
                await self._show_subcommand_help(interaction, "volunteer", subcommand_lower)
                return

        # Handle regular commands
        if command_lower not in self.commands:
            await interaction.response.send_message(
                f"❌ Unknown command: `{command}`\n\n" f"Use `/help` to see all available commands.",
                ephemeral=True,
            )
            return

        cmd_info = self.commands[command_lower]
        status = cmd_info.get("status", "available")

        if status == "coming_soon":
            embed = discord.Embed(
                title=f"🚧 /{command} (Coming Soon)",
                description=cmd_info["description"],
                color=discord.Color.orange(),
            )
            embed.add_field(
                name="Status",
                value="This command is not yet available. Check back soon!",
                inline=False,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Build detailed help embed
        embed = discord.Embed(
            title=f"📖 /{command}",
            description=cmd_info["description"],
            color=discord.Color.green(),
        )

        # Show subcommands if available
        if "subcommands" in cmd_info:
            subcommands_text = ""
            for subcmd_name, subcmd_info in cmd_info["subcommands"].items():
                subcommands_text += f"**{subcmd_name}** - {subcmd_info['description']}\n"
            embed.add_field(name="Subcommands", value=subcommands_text, inline=False)

            # If specific subcommand requested but not found, show error
            if subcommand:
                subcommand_lower = subcommand.lower()
                if subcommand_lower not in cmd_info["subcommands"]:
                    await interaction.response.send_message(
                        f"❌ Unknown subcommand: `{subcommand}` for command `{command}`\n\n"
                        f"Use `/help {command}` to see available subcommands.",
                        ephemeral=True,
                    )
                    return

        # Show parameters
        parameters = cmd_info.get("parameters", {})
        if parameters:
            params_text = ""
            for param_name, param_desc in parameters.items():
                params_text += f"**{param_name}** - {param_desc}\n"
            embed.add_field(name="Parameters", value=params_text, inline=False)

        # Show examples
        examples = cmd_info.get("examples", [])
        if examples:
            examples_text = "\n".join([f"`{ex}`" for ex in examples])
            embed.add_field(name="Examples", value=examples_text, inline=False)

        # Show permissions if applicable
        if "permissions" in cmd_info:
            embed.add_field(name="Permissions", value=cmd_info["permissions"], inline=False)

        # Show note if available
        if "note" in cmd_info:
            embed.add_field(name="Note", value=cmd_info["note"], inline=False)

        embed.set_footer(text="All dates are displayed in PST timezone. Date format: YYYY-MM-DD")

        await interaction.response.send_message(embed=embed)

    async def _show_subcommand_help(
        self,
        interaction: discord.Interaction,
        command: str,
        subcommand: str,
    ) -> None:
        """
        Show detailed help for a subcommand.

        Args:
            interaction: Discord interaction
            command: Command name (e.g., "volunteer")
            subcommand: Subcommand name (e.g., "recurring")
        """
        cmd_info = self.commands.get(command, {})
        subcmd_info = cmd_info.get("subcommands", {}).get(subcommand, {})

        embed = discord.Embed(
            title=f"📖 /{command} {subcommand}",
            description=subcmd_info.get("description", ""),
            color=discord.Color.green(),
        )

        # Show parameters
        parameters = subcmd_info.get("parameters", {})
        if parameters:
            params_text = ""
            for param_name, param_desc in parameters.items():
                params_text += f"**{param_name}** - {param_desc}\n"
            embed.add_field(name="Parameters", value=params_text, inline=False)

        # Show examples
        examples = subcmd_info.get("examples", [])
        if examples:
            examples_text = "\n".join([f"`{ex}`" for ex in examples])
            embed.add_field(name="Examples", value=examples_text, inline=False)

        # Show permissions if applicable
        if "permissions" in subcmd_info:
            embed.add_field(name="Permissions", value=subcmd_info["permissions"], inline=False)

        embed.set_footer(text="All dates are displayed in PST timezone. Date format: YYYY-MM-DD")

        await interaction.response.send_message(embed=embed)


def register_help_command(
    tree: app_commands.CommandTree,
    sheets_service: SheetsService,
    cache_service: CacheService,
    sync_service: SyncService,
    config: dict,
) -> None:
    """
    Register /help command with Discord bot.

    Args:
        tree: Discord command tree
        sheets_service: Google Sheets service instance
        cache_service: Cache service instance
        sync_service: Sync service instance
        config: Configuration dictionary
    """
    handler = HelpCommand(sheets_service, cache_service, sync_service, config)

    @tree.command(
        name="help",
        description="List all available commands or get detailed help for a specific command",
    )
    @app_commands.describe(
        command="Command name to get detailed help for (optional)",
        subcommand="Subcommand name (for commands with subcommands, optional)",
    )
    async def help_command(
        interaction: discord.Interaction,
        command: Optional[str] = None,
        subcommand: Optional[str] = None,
    ):
        """Show help for commands."""
        await handler.handle(interaction, command, subcommand)
