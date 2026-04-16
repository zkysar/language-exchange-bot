from __future__ import annotations

import discord
from discord import app_commands

from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService, make_audit
from src.utils.auth import is_admin
from src.utils.logger import get_logger

log = get_logger(__name__)


def build_command(sheets: SheetsService, cache: CacheService) -> app_commands.Command:
    @app_commands.command(name="sync", description="Force sync with Google Sheets")
    async def sync(interaction: discord.Interaction) -> None:
        if not is_admin(interaction.user, cache.config):
            await interaction.response.send_message(
                "This command requires the admin role.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await cache.refresh(force=True)
            sheets.append_audit(make_audit("SYNC_FORCED", str(interaction.user.id)))
        except Exception:
            log.exception("sync failed")
            await interaction.followup.send(
                "Sync failed. Please try again later.", ephemeral=True
            )
            return
        await interaction.followup.send(
            f"Synced: {len(cache.all_events())} event(s) loaded.", ephemeral=True
        )

    return sync
