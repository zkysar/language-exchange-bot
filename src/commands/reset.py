from __future__ import annotations

import discord
from discord import app_commands

from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService, make_audit
from src.utils.auth import is_admin
from src.utils.logger import get_logger

log = get_logger(__name__)

INSTRUCTIONS = (
    "**Database Reset Procedure**\n\n"
    "1. Google Sheets is the source of truth — verify it is correct first.\n"
    "2. Running `/sync` is usually sufficient; only use reset for corruption.\n"
    "3. Reset clears the in-memory cache and reloads from Google Sheets.\n"
    "4. Confirm by pressing the button below within 30 seconds."
)


class _ConfirmReset(discord.ui.View):
    def __init__(self, sheets: SheetsService, cache: CacheService, invoker: discord.abc.User) -> None:
        super().__init__(timeout=30)
        self.sheets = sheets
        self.cache = cache
        self.invoker = invoker

    @discord.ui.button(label="Confirm Reset", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.invoker.id:
            await interaction.response.send_message("Not your action.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            self.cache.invalidate()
            await self.cache.refresh(force=True)
            self.sheets.append_audit(make_audit("RESET", str(self.invoker.id)))
        except Exception:
            log.exception("reset failed")
            await interaction.followup.send(
                "Reset failed. Please try again later.", ephemeral=True
            )
            return
        self.stop()
        await interaction.followup.send("✅ Reset complete.", ephemeral=True)


def build_command(sheets: SheetsService, cache: CacheService) -> app_commands.Command:
    @app_commands.command(name="reset", description="Display reset procedure and confirm")
    async def reset(interaction: discord.Interaction) -> None:
        if not is_admin(interaction.user, cache.config):
            await interaction.response.send_message(
                "This command requires the admin role.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            INSTRUCTIONS,
            view=_ConfirmReset(sheets, cache, interaction.user),
            ephemeral=True,
        )

    return reset
