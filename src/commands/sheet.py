from __future__ import annotations

import os

import discord
from discord import app_commands


def sheet_url() -> str:
    sid = os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID", "")
    return f"https://docs.google.com/spreadsheets/d/{sid}/edit"


def build_command() -> app_commands.Command:
    @app_commands.command(name="sheet", description="Link to the backing Google Sheet")
    async def sheet_cmd(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            f"[Backing sheet]({sheet_url()})", ephemeral=True
        )

    return sheet_cmd
