from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.commands.reset import _ConfirmReset, build_command
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
    c.invalidate = MagicMock()
    return c


@pytest.mark.asyncio
async def test_reset_non_admin_rejected(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.reset.is_admin", return_value=False):
        await cmd.callback(interaction)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_reset_admin_sends_instructions_with_view(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.reset.is_admin", return_value=True):
        await cmd.callback(interaction)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert "view" in kwargs
    assert isinstance(kwargs["view"], _ConfirmReset)


@pytest.mark.asyncio
async def test_confirm_reset_wrong_invoker_rejected(sheets: MagicMock, cache: MagicMock) -> None:
    invoker = MagicMock(spec=discord.Member)
    invoker.id = 1
    view = _ConfirmReset(sheets, cache, invoker)
    # A different user tries to click confirm
    interaction = make_interaction(user_id=2)
    btn = view.children[0]
    await btn.callback(interaction)
    interaction.response.send_message.assert_awaited_once()
    args, _ = interaction.response.send_message.call_args
    assert "Not your action" in args[0]
    cache.invalidate.assert_not_called()


@pytest.mark.asyncio
async def test_confirm_reset_happy_path(sheets: MagicMock, cache: MagicMock) -> None:
    invoker = MagicMock(spec=discord.Member)
    invoker.id = 1
    view = _ConfirmReset(sheets, cache, invoker)
    interaction = make_interaction(user_id=1)
    btn = view.children[0]
    await btn.callback(interaction)
    cache.invalidate.assert_called_once()
    cache.refresh.assert_awaited_once_with(force=True)
    sheets.append_audit.assert_called_once()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "Reset complete" in args[0]


@pytest.mark.asyncio
async def test_confirm_reset_exception_sends_error(sheets: MagicMock, cache: MagicMock) -> None:
    cache.refresh.side_effect = RuntimeError("network error")
    invoker = MagicMock(spec=discord.Member)
    invoker.id = 1
    view = _ConfirmReset(sheets, cache, invoker)
    interaction = make_interaction(user_id=1)
    btn = view.children[0]
    await btn.callback(interaction)
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "Reset failed" in args[0]
