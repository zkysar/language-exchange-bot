from __future__ import annotations

from pathlib import Path
from typing import Optional

import discord
from discord import app_commands

from src.commands.sheet import sheet_url
from src.services.cache_service import CacheService
from src.utils.auth import is_admin, is_host, is_owner


def _read_version() -> str:
    p = Path("VERSION")
    if p.exists():
        return p.read_text().strip()
    return "dev"


GITHUB_URL = "https://github.com/zkysar/language-exchange-bot"

BOT_DESCRIPTION = (
    "I help coordinate language-exchange hosting. "
    "See who's hosting, volunteer for open dates, "
    "or set up a recurring schedule."
)

VISIBILITY_LEGEND = "🤫 only you see the reply · 📢 the whole channel sees the reply"

COMMAND_HELP = {
    "schedule": "Use `/schedule` to view the next N weeks (default 4, max 12). "
                "Pass `date:YYYY-MM-DD` to check a single date, or `user:@x` to filter "
                "to a specific user's dates (hosts/admins can view others). "
                "Replies are private by default — pass `public:true` to share with the channel.",
    "hosting": "Use `/hosting action:signup date:<date>` to claim an open date, "
               "`/hosting action:signup pattern:'every 2nd Tuesday'` to set up a recurring pattern, "
               "`/hosting action:cancel date:<date>` to cancel a date, or "
               "`/hosting action:cancel pattern:<pattern>` to cancel a recurring pattern. "
               "Confirmations are posted in the channel (📢) so everyone can see the "
               "updated schedule. When `meeting_schedule` is set in config, signups "
               "are restricted to the days the exchange actually meets.",
    "config": "Owner-only. Use `/config` to view all settings, `/config action:set key:<key> value:<v>` "
              "to change a setting, or `/config action:add|remove key:admin|host|member value:<role>` "
              "to manage role buckets. Set `meeting_schedule` (e.g. `every wednesday`) to restrict "
              "signups, schedule view, and warnings to meeting days; leave value empty to clear.",
    "setup": "Owner-only. Guided wizard that walks through all essential bot configuration.",
    "sync": "Admin-only. Forces a full resync of local cache from Google Sheets.",
}

HELP_TEXT = {None: "", **COMMAND_HELP}

_MEMBER_INTRO = (
    "Check who's hosting upcoming sessions and when open dates are available."
)

_MEMBER_CATEGORIES = {
    "Members — View Schedule": [
        ("/schedule [weeks] [date] [user]", "See upcoming hosts"),
    ],
}

_HOST_INTRO = (
    "Sign up when you're willing to run a session. Claim a one-off date or set a "
    "recurring pattern (e.g. \"every 2nd Tuesday\") so the schedule fills itself. "
    "Cancel anytime if plans change — open dates show up for others to claim."
)

_HOST_CATEGORY = (
    "Hosts — Sign Up & Cancel",
    [
        ("/hosting action:signup date:<date>", "Claim a specific date"),
        ("/hosting action:signup pattern:<pattern>", "Set a recurring pattern"),
        ("/hosting action:cancel date:<date>", "Drop a specific date"),
        ("/hosting action:cancel pattern:<pattern>", "Remove a recurring pattern"),
    ],
)

_OTHER_CATEGORY = {
    "Other": [
        ("/help [command]", "Detailed help for a command"),
    ],
}

_ADMIN_INTRO = (
    "You can force a full refresh if the bot's schedule looks stale. "
    "Otherwise the cache updates automatically."
)

_ADMIN_CATEGORY = (
    "Admins — Maintenance",
    [
        ("/sync", "Force sync with Google Sheets"),
    ],
)

_OWNER_INTRO = (
    "Configure which Discord roles map to hosts and admins, "
    "and tweak scheduling defaults. Run `/setup` first on a fresh install."
)

_OWNER_CATEGORY = (
    "Owners — Configuration",
    [
        ("/config show", "View all settings"),
        ("/config set", "Change a setting"),
        ("/config roles", "Manage role buckets"),
        ("/setup", "Guided setup wizard"),
    ],
)

_AUTOCOMPLETE_TIERS = [
    (None, ["schedule"]),
    (is_host, ["hosting"]),
    (is_admin, ["sync"]),
    (is_owner, ["config", "setup"]),
]


def _roles_configured(config) -> bool:
    return bool(config.host_role_ids or config.admin_role_ids)


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
        description=(
            f"{BOT_DESCRIPTION}\n\n"
            f"{VISIBILITY_LEGEND}\n\n"
            f"[Sheet]({sheet_url()}) • [GitHub]({GITHUB_URL})"
        ),
        color=0x5865F2,
    )

    for heading, cmds in _MEMBER_CATEGORIES.items():
        lines = f"*{_MEMBER_INTRO}*\n" + "\n".join(f"`{c}` — {desc}" for c, desc in cmds)
        embed.add_field(name=heading, value=lines, inline=False)
    if is_host(user, config):
        heading, cmds = _HOST_CATEGORY
        lines = f"*{_HOST_INTRO}*\n" + "\n".join(f"`{c}` — {desc}" for c, desc in cmds)
        embed.add_field(name=heading, value=lines, inline=False)
    if is_admin(user, config):
        heading, cmds = _ADMIN_CATEGORY
        lines = f"*{_ADMIN_INTRO}*\n" + "\n".join(f"`{c}` — {desc}" for c, desc in cmds)
        embed.add_field(name=heading, value=lines, inline=False)
    if is_owner(user, config):
        heading, cmds = _OWNER_CATEGORY
        lines = f"*{_OWNER_INTRO}*\n" + "\n".join(f"`{c}` — {desc}" for c, desc in cmds)
        embed.add_field(name=heading, value=lines, inline=False)
    if not _roles_configured(config):
        embed.add_field(
            name="Not configured",
            value=(
                "No roles are set up yet. An owner needs to run "
                "`/setup` to assign admin and host roles."
            ),
            inline=False,
        )

    for heading, cmds in _OTHER_CATEGORY.items():
        lines = "\n".join(f"`{c}` — {desc}" for c, desc in cmds)
        embed.add_field(name=heading, value=lines, inline=False)

    embed.set_footer(text=_read_version())
    return embed


def build_command(cache: CacheService) -> app_commands.Command:
    @app_commands.command(name="help", description="🤫 Show command help")
    @app_commands.describe(command="Pick a command for details")
    async def help_cmd(
        interaction: discord.Interaction,
        command: Optional[str] = None,
    ) -> None:
        if command:
            text = COMMAND_HELP.get(command)
            if text:
                text = f"{text}\n\n[Sheet]({sheet_url()}) • [GitHub]({GITHUB_URL})"
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
