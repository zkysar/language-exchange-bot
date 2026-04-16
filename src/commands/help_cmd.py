from __future__ import annotations

from pathlib import Path
from typing import Optional

import discord
from discord import app_commands

from src.commands.sheet import sheet_url
from src.services.cache_service import CacheService
from src.utils.auth import is_admin, is_host, is_member, is_owner


def _read_version() -> str:
    p = Path("VERSION")
    if p.exists():
        return p.read_text().strip()
    return "dev"


BOT_DESCRIPTION = (
    "I help coordinate language-exchange hosting. "
    "See who's hosting, volunteer for open dates, "
    "or set up a recurring schedule."
)

COMMAND_HELP = {
    "schedule": "Use `/schedule` to view the next N weeks (default 4, max 12). "
                "Pass `date:YYYY-MM-DD` to check a single date, or `user:@x` to filter "
                "to a specific user's dates (hosts/admins can view others).",
    "warnings": "Use `/warnings` to see any unassigned dates within the warning window. "
                "Response is always private.",
    "volunteer": "Use `/volunteer date` to claim an open date from the autocomplete dropdown, "
                 "or `/volunteer recurring pattern:'every 2nd Tuesday'` to set up a pattern.",
    "unvolunteer": "Use `/unvolunteer date` to cancel a specific hosting commitment, or "
                   "`/unvolunteer recurring` to cancel a recurring pattern (clears future dates).",
    "sheet": "Shows the URL of the backing Google Sheet. You need to be "
             "granted view access to actually open it.",
    "config": "Owner-only. Use `/config show` to see all settings, or `/config warnings`, "
              "`/config schedule`, `/config channels`, `/config roles` to change values.",
    "setup": "Owner-only. Guided wizard that walks through all essential bot configuration.",
    "sync": "Admin-only. Forces a full resync of local cache from Google Sheets.",
    "reset": "Admin-only. Displays the reset procedure and requires confirmation.",
}

HELP_TEXT = {None: "", **COMMAND_HELP}

_MEMBER_CATEGORIES = {
    "View Schedule": [
        ("/schedule [weeks] [date] [user]", "See upcoming hosts"),
        ("/warnings", "Dates that still need a host"),
    ],
}

_HOST_CATEGORY = (
    "Volunteer",
    [
        ("/volunteer date", "Sign up for an open date"),
        ("/volunteer recurring", "Set a recurring pattern"),
        ("/unvolunteer date", "Cancel a specific date"),
        ("/unvolunteer recurring", "Cancel your recurring pattern"),
    ],
)

_OTHER_CATEGORY = {
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

_OWNER_CATEGORY = (
    "Owner",
    [
        ("/config show", "View all configuration"),
        ("/config <group> <setting>", "Change a setting"),
        ("/setup", "Guided setup wizard"),
    ],
)

_AUTOCOMPLETE_TIERS = [
    (None, ["sheet"]),
    (is_member, ["schedule", "warnings"]),
    (is_host, ["volunteer", "unvolunteer"]),
    (is_admin, ["sync", "reset"]),
    (is_owner, ["config", "setup"]),
]


def _roles_configured(config) -> bool:
    return bool(config.member_role_ids or config.host_role_ids or config.admin_role_ids)


def _visible_autocomplete(user: discord.abc.User, config) -> list[str]:
    visible: list[str] = []
    for check, names in _AUTOCOMPLETE_TIERS:
        if check is not None and not check(user, config):
            continue
        visible.extend(names)
    return visible


def _build_embed(user: discord.abc.User, config) -> discord.Embed:
    embed = discord.Embed(
        title="Host Scheduler",
        description=BOT_DESCRIPTION,
        color=0x5865F2,
    )

    if _roles_configured(config):
        if is_member(user, config):
            for heading, cmds in _MEMBER_CATEGORIES.items():
                lines = "\n".join(f"`{c}` — {desc}" for c, desc in cmds)
                embed.add_field(name=heading, value=lines, inline=False)
        if is_host(user, config):
            heading, cmds = _HOST_CATEGORY
            lines = "\n".join(f"`{c}` — {desc}" for c, desc in cmds)
            embed.add_field(name=heading, value=lines, inline=False)
        if is_admin(user, config):
            heading, cmds = _ADMIN_CATEGORY
            lines = "\n".join(f"`{c}` — {desc}" for c, desc in cmds)
            embed.add_field(name=heading, value=lines, inline=False)
        if is_owner(user, config):
            heading, cmds = _OWNER_CATEGORY
            lines = "\n".join(f"`{c}` — {desc}" for c, desc in cmds)
            embed.add_field(name=heading, value=lines, inline=False)
    else:
        embed.add_field(
            name="Not configured",
            value=(
                "No roles are set up yet. An owner needs to run "
                "`/setup` to assign admin, host, and member roles "
                "before most commands will work."
            ),
            inline=False,
        )

    for heading, cmds in _OTHER_CATEGORY.items():
        lines = "\n".join(f"`{c}` — {desc}" for c, desc in cmds)
        embed.add_field(name=heading, value=lines, inline=False)

    embed.set_footer(text=f"{_read_version()} · Sheet: {sheet_url()}")
    return embed


def build_command(cache: CacheService) -> app_commands.Command:
    @app_commands.command(name="help", description="Show command help")
    @app_commands.describe(command="Pick a command for details")
    async def help_cmd(
        interaction: discord.Interaction,
        command: Optional[str] = None,
    ) -> None:
        if command:
            text = COMMAND_HELP.get(command)
            if text:
                text = f"{text}\n\nSheet: {sheet_url()}"
                await interaction.response.send_message(text, ephemeral=True)
                return

        embed = _build_embed(interaction.user, cache.config)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @help_cmd.autocomplete("command")
    async def _command_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        visible = _visible_autocomplete(interaction.user, cache.config)
        return [
            app_commands.Choice(name=name, value=name)
            for name in visible
            if current.lower() in name.lower()
        ][:25]

    return help_cmd
