from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands

from src.commands.sheet import sheet_url
from src.services.cache_service import CacheService
from src.utils.auth import is_admin, is_host, is_member, is_owner

COMMAND_DETAIL = {
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
    "setup": "Owner-only. Configure admin/host/member role mappings.",
    "sheet": "Shows the URL of the backing Google Sheet. You need to be "
             "granted view access to actually open it.",
}

TIERED_COMMANDS = [
    (None, [
        ("help", "• `/help [command]` — This help"),
        ("sheet", "• `/sheet` — Link to the backing Google Sheet"),
    ]),
    (is_member, [
        ("schedule", "• `/schedule [weeks] [date]` — View upcoming host schedule"),
        ("listdates", "• `/listdates [user]` — Upcoming dates for a user"),
        ("warnings", "• `/warnings` — Check unassigned dates needing hosts"),
    ]),
    (is_host, [
        ("volunteer", "• `/volunteer date` / `/volunteer recurring` — Sign up to host"),
        ("unvolunteer", "• `/unvolunteer date` / `/unvolunteer recurring` — Cancel hosting"),
    ]),
    (is_admin, [
        ("sync", "• `/sync` — Force sync with Google Sheets"),
        ("reset", "• `/reset` — Reset database cache"),
    ]),
    (is_owner, [
        ("setup", "• `/setup` — Configure role mappings"),
    ]),
]


def _visible_commands(user: discord.abc.User, config) -> tuple[list[str], list[str]]:
    lines: list[str] = []
    visible: list[str] = []
    for check, entries in TIERED_COMMANDS:
        if check is not None and not check(user, config):
            continue
        for name, line in entries:
            lines.append(line)
            visible.append(name)
    return lines, visible


def _roles_configured(config) -> bool:
    return bool(config.member_role_ids or config.host_role_ids or config.admin_role_ids)


def _build_overview(user: discord.abc.User, config) -> str:
    lines, _ = _visible_commands(user, config)
    text = "**Commands**\n" + "\n".join(lines)
    if not _roles_configured(config):
        text += (
            "\n\n⚠️ **No roles are configured yet.** "
            "An owner needs to run `/setup` to assign admin, host, "
            "and member roles before most commands will work."
        )
    return text


def build_command(cache: CacheService) -> app_commands.Command:
    @app_commands.command(name="help", description="Show command help")
    @app_commands.describe(command="Pick a command for details")
    async def help_cmd(
        interaction: discord.Interaction,
        command: Optional[str] = None,
    ) -> None:
        if command:
            text = COMMAND_DETAIL.get(command)
            if not text:
                text = _build_overview(interaction.user, cache.config)
        else:
            text = _build_overview(interaction.user, cache.config)
        text = f"{text}\n\nSheet: {sheet_url()}"
        await interaction.response.send_message(text, ephemeral=True)

    @help_cmd.autocomplete("command")
    async def _command_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        _, visible = _visible_commands(interaction.user, cache.config)
        return [
            app_commands.Choice(name=name, value=name)
            for name in visible
            if name != "help" and current.lower() in name.lower()
        ][:25]

    return help_cmd
