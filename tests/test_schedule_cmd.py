from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.commands.schedule import build_command
from src.models.models import Configuration, EventDate


def make_interaction(user_id: int = 1) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = user_id
    interaction.guild = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    return interaction


@pytest.fixture
def cache() -> MagicMock:
    c = MagicMock()
    c.config = Configuration.default()
    c.refresh = AsyncMock()
    c.all_events = MagicMock(return_value=[])
    c.get_event = MagicMock(return_value=None)
    return c


@pytest.mark.asyncio
async def test_schedule_member_cannot_view_other_user_dates(cache: MagicMock) -> None:
    cmd = build_command(cache)
    interaction = make_interaction(user_id=1)
    other_user = MagicMock(spec=discord.User)
    other_user.id = 2
    with patch("src.commands.schedule.is_host", return_value=False):
        await cmd.callback(interaction, weeks=None, date=None, user=other_user)
    args, kwargs = interaction.response.send_message.call_args
    assert "only" in args[0].lower() or "own" in args[0].lower()
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_schedule_invalid_date_format_rejected(cache: MagicMock) -> None:
    cmd = build_command(cache)
    interaction = make_interaction()
    with patch("src.commands.schedule.is_host", return_value=True):
        await cmd.callback(interaction, weeks=None, date="not-a-date", user=None)
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_schedule_specific_date_assigned(cache: MagicMock) -> None:
    ev = EventDate(date=date(2025, 6, 10), host_discord_id="42")
    cache.get_event = MagicMock(return_value=ev)
    cmd = build_command(cache)
    interaction = make_interaction()
    with patch("src.commands.schedule.is_host", return_value=True):
        await cmd.callback(interaction, weeks=None, date="2025-06-10", user=None)
    args, _ = interaction.response.send_message.call_args
    assert "<@42>" in args[0]


@pytest.mark.asyncio
async def test_schedule_specific_date_unassigned(cache: MagicMock) -> None:
    cache.get_event = MagicMock(return_value=None)
    cmd = build_command(cache)
    interaction = make_interaction()
    with patch("src.commands.schedule.is_host", return_value=True):
        await cmd.callback(interaction, weeks=None, date="2025-06-10", user=None)
    args, _ = interaction.response.send_message.call_args
    assert "unassigned" in args[0]


@pytest.mark.asyncio
async def test_schedule_empty_timeline(cache: MagicMock) -> None:
    cache.all_events = MagicMock(return_value=[])
    cmd = build_command(cache)
    interaction = make_interaction()
    with (
        patch("src.commands.schedule.is_host", return_value=True),
        patch("src.commands.schedule.today_la", return_value=date(2025, 6, 10)),
    ):
        await cmd.callback(interaction, weeks=1, date=None, user=None)
    args, _ = interaction.response.send_message.call_args
    assert "Schedule" in args[0]


@pytest.mark.asyncio
async def test_schedule_weeks_zero_falls_back_to_config_default(cache: MagicMock) -> None:
    # weeks=0 is falsy, so the code uses cache.config.schedule_window_weeks (default 2)
    cache.all_events = MagicMock(return_value=[])
    cache.config.schedule_window_weeks = 2
    cmd = build_command(cache)
    interaction = make_interaction()
    with (
        patch("src.commands.schedule.is_host", return_value=True),
        patch("src.commands.schedule.today_la", return_value=date(2025, 6, 10)),
    ):
        await cmd.callback(interaction, weeks=0, date=None, user=None)
    interaction.response.send_message.assert_awaited_once()
    args, _ = interaction.response.send_message.call_args
    assert "2 week" in args[0]


@pytest.mark.asyncio
async def test_schedule_truncates_output_beyond_60_lines(cache: MagicMock) -> None:
    # 12 weeks = 84 days + 1 header = 85 lines > 60, triggers truncation
    cache.all_events = MagicMock(return_value=[])
    cmd = build_command(cache)
    interaction = make_interaction()
    with (
        patch("src.commands.schedule.is_host", return_value=True),
        patch("src.commands.schedule.today_la", return_value=date(2025, 6, 1)),
    ):
        await cmd.callback(interaction, weeks=12, date=None, user=None)
    args, _ = interaction.response.send_message.call_args
    assert "more" in args[0]


@pytest.mark.asyncio
async def test_schedule_filters_by_target_user(cache: MagicMock) -> None:
    events = [
        EventDate(date=date(2025, 6, 10), host_discord_id="42"),
        EventDate(date=date(2025, 6, 11), host_discord_id="99"),
    ]
    cache.all_events = MagicMock(return_value=events)
    cmd = build_command(cache)
    interaction = make_interaction(user_id=1)
    target = MagicMock(spec=discord.User)
    target.id = 42
    with (
        patch("src.commands.schedule.is_host", return_value=True),
        patch("src.commands.schedule.today_la", return_value=date(2025, 6, 1)),
    ):
        await cmd.callback(interaction, weeks=4, date=None, user=target)
    args, _ = interaction.response.send_message.call_args
    assert "<@42>" in args[0]


@pytest.mark.asyncio
async def test_schedule_no_matches_for_target_user(cache: MagicMock) -> None:
    cache.all_events = MagicMock(return_value=[])
    cmd = build_command(cache)
    interaction = make_interaction(user_id=1)
    target = MagicMock(spec=discord.User)
    target.id = 42
    with (
        patch("src.commands.schedule.is_host", return_value=True),
        patch("src.commands.schedule.today_la", return_value=date(2025, 6, 1)),
    ):
        await cmd.callback(interaction, weeks=4, date=None, user=target)
    args, _ = interaction.response.send_message.call_args
    assert "no upcoming" in args[0].lower()
