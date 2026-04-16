from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands

from src.commands.sheet import sheet_url
from src.services.cache_service import CacheService
from src.utils.auth import is_admin

BOT_DESCRIPTION = (
    "I help coordinate language-exchange hosting. "
    "See who's hosting, volunteer for open dates, "
    "or set up a recurring schedule."
)

COMMAND_HELP = {
    "schedule": "Use `/schedule` to view the next N weeks (default 4, max 12). "
                "Pass `date:YYYY-MM-DD` to check a single date.",
    "listdates": "Use `/listdates` to view your upcoming dates, or `/listdates user:@x` "
                 "(hosts/admins only) to view another user.",
    "warnings": "Use `/warnings` to see any unassigned dates within the warning window. "
                "Response is always private.",
    "volunteer": "Use `/volunteer date` to claim an open date from the autocomplete dropdown, "
                 "or `/volunteer recurring pattern:'every 2nd Tuesday'` to set up a pattern.",
    "unvolunteer": "Use `/unvolunteer date` to cancel a specific hosting commitment, or "
                   "`/unvolunteer recurring` to cancel a recurring pattern (clears future dates).",
    "sheet": "Shows the URL of the backing Google Sheet. You need to be "
             "granted view access to actually open it.",
    "sync": "Admin-only. Forces a full resync of local cache from Google Sheets.",
    "reset": "Admin-only. Displays the reset procedure and requires confirmation.",
}

HELP_TEXT = {None: "", **COMMAND_HELP}

_CATEGORIES = {
    "View Schedule": [
        ("/schedule [weeks] [date]", "See upcoming hosts"),
        ("/listdates [user]", "Your upcoming dates"),
        ("/warnings", "Dates that still need a host"),
    ],
    "Volunteer": [
        ("/volunteer date", "Sign up for an open date"),
        ("/volunteer recurring", "Set a recurring pattern"),
        ("/unvolunteer date", "Cancel a specific date"),
        ("/unvolunteer recurring", "Cancel your recurring pattern"),
    ],
    "Other": [
        ("/sheet", "Link to the Google Sheet"),
        ("/help [command]", "Detailed help for a command"),
    ],
}

_ADMIN_CATEGORY = (
    "Admin",
    [
        ("/sync", "Force sync with Google Sheets"),
        ("/reset", "Reset the database cache"),
    ],
)


def _build_embed(show_admin: bool) -> discord.Embed:
    embed = discord.Embed(
        title="Host Scheduler",
        description=BOT_DESCRIPTION,
        color=0x5865F2,
    )
    for heading, cmds in _CATEGORIES.items():
        lines = "\n".join(f"`{c}` — {desc}" for c, desc in cmds)
        embed.add_field(name=heading, value=lines, inline=False)
    if show_admin:
        heading, cmds = _ADMIN_CATEGORY
        lines = "\n".join(f"`{c}` — {desc}" for c, desc in cmds)
        embed.add_field(name=heading, value=lines, inline=False)
    embed.set_footer(text=f"Sheet: {sheet_url()}")
    return embed


_COMMAND_CHOICES = [
    app_commands.Choice(name=key, value=key)
    for key in COMMAND_HELP
]


def build_command(cache: CacheService) -> app_commands.Command:
    @app_commands.command(name="help", description="Show command help")
    @app_commands.describe(command="Pick a command for details")
    @app_commands.choices(command=_COMMAND_CHOICES)
    async def help_cmd(
        interaction: discord.Interaction,
        command: Optional[app_commands.Choice[str]] = None,
    ) -> None:
        if command:
            text = COMMAND_HELP.get(command.value, COMMAND_HELP.get("schedule"))
            text = f"{text}\n\nSheet: {sheet_url()}"
            await interaction.response.send_message(text, ephemeral=True)
            return

        show_admin = is_admin(interaction.user, cache.config)
        embed = _build_embed(show_admin)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    return help_cmd
