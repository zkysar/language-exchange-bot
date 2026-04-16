from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands

HELP_TEXT = {
    None: (
        "**Commands**\n"
        "• `/schedule [weeks] [date]` — View upcoming host schedule\n"
        "• `/listdates [user]` — Upcoming dates for a user\n"
        "• `/warnings` — Check unassigned dates needing hosts\n"
        "• `/volunteer date date:[date] [user]` — Sign up for an open date\n"
        "• `/volunteer recurring pattern:[pattern] [user]` — Recurring pattern\n"
        "• `/unvolunteer date date:[date] [user]` — Cancel a date\n"
        "• `/unvolunteer recurring [user]` — Cancel recurring pattern\n"
        "• `/sync` — (admin) Force sync with Google Sheets\n"
        "• `/reset` — (admin) Reset database cache\n"
        "• `/help [command]` — This help"
    ),
    "volunteer": "Use `/volunteer date` to claim an open date from the autocomplete dropdown, "
                 "or `/volunteer recurring pattern:'every 2nd Tuesday'` to set up a pattern.",
    "unvolunteer": "Use `/unvolunteer date` to cancel a specific hosting commitment, or "
                   "`/unvolunteer recurring` to cancel a recurring pattern (clears future dates).",
    "schedule": "Use `/schedule` to view the next N weeks (default 4, max 12). "
                "Pass `date:YYYY-MM-DD` to check a single date.",
    "warnings": "Use `/warnings` to see any unassigned dates within the warning window. "
                "Response is always private.",
    "listdates": "Use `/listdates` to view your upcoming dates, or `/listdates user:@x` "
                 "(hosts/admins only) to view another user.",
    "sync": "Admin-only. Forces a full resync of local cache from Google Sheets.",
    "reset": "Admin-only. Displays the reset procedure and requires confirmation.",
}


_COMMAND_CHOICES = [
    app_commands.Choice(name=key, value=key)
    for key in HELP_TEXT
    if key is not None
]


def build_command() -> app_commands.Command:
    @app_commands.command(name="help", description="Show command help")
    @app_commands.describe(command="Pick a command for details")
    @app_commands.choices(command=_COMMAND_CHOICES)
    async def help_cmd(
        interaction: discord.Interaction,
        command: Optional[app_commands.Choice[str]] = None,
    ) -> None:
        key = command.value if command else None
        text = HELP_TEXT.get(key)
        if not text:
            text = HELP_TEXT[None]
        await interaction.response.send_message(text, ephemeral=True)

    return help_cmd
