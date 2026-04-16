from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.commands.sync import build_command
from src.models.models import Configuration


def make_interaction(user_id: int = 1) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = user_id
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.fixture
def sheets() -> MagicMock:
    return MagicMock()


@pytest.fixture
def cache() -> MagicMock:
    c = MagicMock()
    c.config = Configuration.default()
    c.refresh = AsyncMock()
    c.all_events = MagicMock(return_value=[])
    return c


@pytest.mark.asyncio
async def test_sync_non_admin_rejected(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.sync.is_admin", return_value=False):
        await cmd.callback(interaction)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
    cache.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_happy_path(sheets: MagicMock, cache: MagicMock) -> None:
    cache.all_events.return_value = [MagicMock(), MagicMock(), MagicMock()]
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.sync.is_admin", return_value=True):
        await cmd.callback(interaction)
    cache.refresh.assert_awaited_once_with(force=True)
    sheets.append_audit.assert_called_once()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "3" in args[0]


@pytest.mark.asyncio
async def test_sync_exception_sends_error_no_audit(sheets: MagicMock, cache: MagicMock) -> None:
    cache.refresh.side_effect = RuntimeError("sheets unavailable")
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.sync.is_admin", return_value=True):
        await cmd.callback(interaction)
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "Sync failed" in args[0]
    sheets.append_audit.assert_not_called()


@pytest.mark.asyncio
async def test_sync_defers_before_work(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.sync.is_admin", return_value=True):
        await cmd.callback(interaction)
    interaction.response.defer.assert_awaited_once()
