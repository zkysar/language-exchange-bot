from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.commands.unvolunteer import build_group
from src.models.models import Configuration, EventDate, RecurringPattern
from src.services.warning_service import WarningItem


def make_interaction(user_id: int = 1) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = user_id
    interaction.data = {"options": []}
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.fixture
def sheets() -> MagicMock:
    s = MagicMock()
    s.write_lock = asyncio.Lock()
    s.delete_future_pattern_rows = MagicMock(return_value=2)
    return s


@pytest.fixture
def cache() -> MagicMock:
    c = MagicMock()
    c.config = Configuration.default()
    c.refresh = AsyncMock()
    c.all_events = MagicMock(return_value=[])
    c.get_event = MagicMock(return_value=None)
    c.remove_event_assignment = MagicMock()
    c.active_patterns_for = MagicMock(return_value=[])
    c.deactivate_pattern = MagicMock()
    c.invalidate = MagicMock()
    return c


@pytest.fixture
def warnings_svc() -> MagicMock:
    w = MagicMock()
    w.check = AsyncMock(return_value=[])
    return w


# ── user_dates_autocomplete ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_user_dates_autocomplete_returns_assigned_future_dates(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    events = [
        EventDate(date=date(2025, 6, 10), host_discord_id="1"),
        EventDate(date=date(2025, 5, 1), host_discord_id="1"),  # past, should be skipped
        EventDate(date=date(2025, 6, 11), host_discord_id="99"),  # different user
    ]
    cache.all_events.return_value = events
    group = build_group(sheets, cache, warnings_svc)
    date_cmd = group.get_command("date")
    autocomplete = date_cmd._params["date"].autocomplete
    interaction = make_interaction(user_id=1)
    with patch("src.commands.unvolunteer.today_la", return_value=date(2025, 6, 1)):
        results = await autocomplete(interaction, "")
    result_values = [c.value for c in results]
    assert "2025-06-10" in result_values
    assert "2025-05-01" not in result_values  # past
    assert "2025-06-11" not in result_values  # different user


@pytest.mark.asyncio
async def test_user_dates_autocomplete_respects_max_25(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    events = [
        EventDate(date=date(2025, 6, i + 1), host_discord_id="1")
        for i in range(30)
    ]
    cache.all_events.return_value = events
    group = build_group(sheets, cache, warnings_svc)
    date_cmd = group.get_command("date")
    autocomplete = date_cmd._params["date"].autocomplete
    interaction = make_interaction(user_id=1)
    with patch("src.commands.unvolunteer.today_la", return_value=date(2025, 5, 1)):
        results = await autocomplete(interaction, "")
    assert len(results) <= 25


# ── unvolunteer date ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unvolunteer_date_non_host_rejected(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    group = build_group(sheets, cache, warnings_svc)
    date_cmd = group.get_command("date")
    interaction = make_interaction()
    with patch("src.commands.unvolunteer.is_host", return_value=False):
        await date_cmd.callback(interaction, date="2025-06-10", user=None)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_unvolunteer_date_invalid_date_rejected(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    group = build_group(sheets, cache, warnings_svc)
    date_cmd = group.get_command("date")
    interaction = make_interaction()
    with patch("src.commands.unvolunteer.is_host", return_value=True):
        await date_cmd.callback(interaction, date="bad-date", user=None)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_unvolunteer_date_not_assigned_sends_error(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cache.get_event.return_value = None
    group = build_group(sheets, cache, warnings_svc)
    date_cmd = group.get_command("date")
    interaction = make_interaction()
    with patch("src.commands.unvolunteer.is_host", return_value=True):
        await date_cmd.callback(interaction, date="2025-06-10", user=None)
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "No one" in args[0] or "scheduled" in args[0].lower()


@pytest.mark.asyncio
async def test_unvolunteer_date_wrong_user_sends_error(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    ev = EventDate(date=date(2025, 6, 10), host_discord_id="99")
    cache.get_event.return_value = ev
    group = build_group(sheets, cache, warnings_svc)
    date_cmd = group.get_command("date")
    interaction = make_interaction(user_id=1)  # user 1 trying to unvolunteer user 99's slot
    with patch("src.commands.unvolunteer.is_host", return_value=True):
        await date_cmd.callback(interaction, date="2025-06-10", user=None)
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "<@99>" in args[0] or "not assigned" in args[0].lower()


@pytest.mark.asyncio
async def test_unvolunteer_date_happy_path(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    ev = EventDate(date=date(2025, 6, 10), host_discord_id="1")
    cache.get_event.return_value = ev
    group = build_group(sheets, cache, warnings_svc)
    date_cmd = group.get_command("date")
    interaction = make_interaction(user_id=1)
    with patch("src.commands.unvolunteer.is_host", return_value=True):
        await date_cmd.callback(interaction, date="2025-06-10", user=None)
    cache.remove_event_assignment.assert_called_once()
    sheets.clear_schedule_assignment.assert_called_once()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "Removed" in args[0]


@pytest.mark.asyncio
async def test_unvolunteer_date_appends_urgent_warning(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    target_date = date(2025, 6, 10)
    ev = EventDate(date=target_date, host_discord_id="1")
    cache.get_event.return_value = ev
    urgent_item = WarningItem(event_date=target_date, days_until=1, severity="urgent")
    warnings_svc.check.return_value = [urgent_item]
    group = build_group(sheets, cache, warnings_svc)
    date_cmd = group.get_command("date")
    interaction = make_interaction(user_id=1)
    with patch("src.commands.unvolunteer.is_host", return_value=True):
        await date_cmd.callback(interaction, date="2025-06-10", user=None)
    args, _ = interaction.followup.send.call_args
    assert "urgent" in args[0].lower() or "⚠️" in args[0]


# ── unvolunteer recurring ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unvolunteer_recurring_non_host_rejected(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    group = build_group(sheets, cache, warnings_svc)
    recurring_cmd = group.get_command("recurring")
    interaction = make_interaction()
    with patch("src.commands.unvolunteer.is_host", return_value=False):
        await recurring_cmd.callback(interaction, user=None)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_unvolunteer_recurring_no_patterns_sends_error(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cache.active_patterns_for.return_value = []
    group = build_group(sheets, cache, warnings_svc)
    recurring_cmd = group.get_command("recurring")
    interaction = make_interaction(user_id=1)
    with patch("src.commands.unvolunteer.is_host", return_value=True):
        await recurring_cmd.callback(interaction, user=None)
    interaction.response.send_message.assert_awaited_once()
    args, _ = interaction.response.send_message.call_args
    assert "no active" in args[0].lower()


@pytest.mark.asyncio
async def test_unvolunteer_recurring_happy_path(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    pattern = RecurringPattern(
        pattern_id="p-123",
        host_discord_id="1",
        host_username="TestUser",
        pattern_description="every monday",
        pattern_rule="weekly:0",
        start_date=date(2025, 6, 2),
        is_active=True,
    )
    cache.active_patterns_for.return_value = [pattern]
    group = build_group(sheets, cache, warnings_svc)
    recurring_cmd = group.get_command("recurring")
    interaction = make_interaction(user_id=1)
    with (
        patch("src.commands.unvolunteer.is_host", return_value=True),
        patch("src.commands.unvolunteer.today_la", return_value=date(2025, 6, 1)),
    ):
        await recurring_cmd.callback(interaction, user=None)
    sheets.deactivate_pattern.assert_called_once_with("p-123")
    sheets.delete_future_pattern_rows.assert_called_once()
    cache.deactivate_pattern.assert_called_once_with("p-123")
    cache.invalidate.assert_called_once()
    cache.refresh.assert_awaited()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "Deactivated" in args[0]
