from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.commands.warnings_cmd import build_command
from src.models.models import Configuration
from src.services.warning_service import WarningItem


def make_interaction(user_id: int = 1) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = user_id
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    return interaction


@pytest.fixture
def cache() -> MagicMock:
    c = MagicMock()
    c.config = Configuration.default()
    return c


@pytest.fixture
def warnings_svc() -> MagicMock:
    w = MagicMock()
    w.check = AsyncMock(return_value=[])
    return w


@pytest.mark.asyncio
async def test_warnings_non_member_rejected(cache: MagicMock, warnings_svc: MagicMock) -> None:
    cmd = build_command(cache, warnings_svc)
    interaction = make_interaction()
    with patch("src.commands.warnings_cmd.is_member", return_value=False):
        await cmd.callback(interaction)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
    warnings_svc.check.assert_not_awaited()


@pytest.mark.asyncio
async def test_warnings_no_items_sends_all_clear(cache: MagicMock, warnings_svc: MagicMock) -> None:
    warnings_svc.check.return_value = []
    cmd = build_command(cache, warnings_svc)
    interaction = make_interaction()
    with patch("src.commands.warnings_cmd.is_member", return_value=True):
        await cmd.callback(interaction)
    args, _ = interaction.response.send_message.call_args
    assert "No warnings" in args[0] or "covered" in args[0]


@pytest.mark.asyncio
async def test_warnings_urgent_shows_siren_icon(cache: MagicMock, warnings_svc: MagicMock) -> None:
    item = WarningItem(event_date=date(2025, 6, 10), days_until=1, severity="urgent")
    warnings_svc.check.return_value = [item]
    cmd = build_command(cache, warnings_svc)
    interaction = make_interaction()
    with patch("src.commands.warnings_cmd.is_member", return_value=True):
        await cmd.callback(interaction)
    args, _ = interaction.response.send_message.call_args
    assert "🚨" in args[0]


@pytest.mark.asyncio
async def test_warnings_passive_shows_warning_icon(cache: MagicMock, warnings_svc: MagicMock) -> None:
    item = WarningItem(event_date=date(2025, 6, 10), days_until=3, severity="passive")
    warnings_svc.check.return_value = [item]
    cmd = build_command(cache, warnings_svc)
    interaction = make_interaction()
    with patch("src.commands.warnings_cmd.is_member", return_value=True):
        await cmd.callback(interaction)
    args, _ = interaction.response.send_message.call_args
    assert "⚠️" in args[0]


@pytest.mark.asyncio
async def test_warnings_shows_days_and_severity_in_output(
    cache: MagicMock, warnings_svc: MagicMock
) -> None:
    item = WarningItem(event_date=date(2025, 6, 10), days_until=2, severity="passive")
    warnings_svc.check.return_value = [item]
    cmd = build_command(cache, warnings_svc)
    interaction = make_interaction()
    with patch("src.commands.warnings_cmd.is_member", return_value=True):
        await cmd.callback(interaction)
    args, _ = interaction.response.send_message.call_args
    assert "2" in args[0]
    assert "passive" in args[0]
