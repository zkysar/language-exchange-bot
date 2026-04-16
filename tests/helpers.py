from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord


def make_interaction(user_id: int = 1, guild: bool = True) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = user_id
    interaction.user.display_name = f"User{user_id}"
    interaction.data = {"options": []}
    interaction.guild = MagicMock() if guild else None
    interaction.namespace = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction
