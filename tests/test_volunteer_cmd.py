from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.commands.volunteer import _ConfirmView, build_group
from src.models.models import Configuration, EventDate
from src.utils.pattern_parser import ParsedPattern


def make_interaction(user_id: int = 1) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = user_id
    interaction.user.display_name = "TestUser"
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
    return s


@pytest.fixture
def cache() -> MagicMock:
    c = MagicMock()
    c.config = Configuration.default()
    c.refresh = AsyncMock()
    c.all_events = MagicMock(return_value=[])
    c.get_event = MagicMock(return_value=None)
    c.upsert_event = MagicMock()
    c.add_pattern = MagicMock()
    c.sheets = MagicMock()
    c.sheets.load_schedule = MagicMock()
    return c


# ── open_date_autocomplete ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_open_date_autocomplete_returns_at_most_25(
    sheets: MagicMock, cache: MagicMock
) -> None:
    group = build_group(sheets, cache)
    date_cmd = group.get_command("date")
    autocomplete = date_cmd._params["date"].autocomplete
    cache.all_events.return_value = []
    interaction = make_interaction()
    with patch("src.commands.volunteer.today_la", return_value=date(2025, 6, 1)):
        results = await autocomplete(interaction, "")
    assert len(results) <= 25


@pytest.mark.asyncio
async def test_open_date_autocomplete_skips_assigned_dates(
    sheets: MagicMock, cache: MagicMock
) -> None:
    events = [EventDate(date=date(2025, 6, 2), host_discord_id="42")]
    cache.all_events.return_value = events
    group = build_group(sheets, cache)
    date_cmd = group.get_command("date")
    autocomplete = date_cmd._params["date"].autocomplete
    interaction = make_interaction()
    with patch("src.commands.volunteer.today_la", return_value=date(2025, 6, 1)):
        results = await autocomplete(interaction, "")
    result_values = [c.value for c in results]
    assert "2025-06-02" not in result_values


@pytest.mark.asyncio
async def test_open_date_autocomplete_filters_by_prefix(
    sheets: MagicMock, cache: MagicMock
) -> None:
    cache.all_events.return_value = []
    group = build_group(sheets, cache)
    date_cmd = group.get_command("date")
    autocomplete = date_cmd._params["date"].autocomplete
    interaction = make_interaction()
    with patch("src.commands.volunteer.today_la", return_value=date(2025, 6, 1)):
        results_all = await autocomplete(interaction, "")
        results_filtered = await autocomplete(interaction, "Jun 01")
    assert len(results_filtered) <= len(results_all)


# ── volunteer date ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_volunteer_date_non_host_rejected(
    sheets: MagicMock, cache: MagicMock
) -> None:
    group = build_group(sheets, cache)
    date_cmd = group.get_command("date")
    interaction = make_interaction()
    with patch("src.commands.volunteer.is_host", return_value=False):
        await date_cmd.callback(interaction, date="2025-06-10", user=None)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_volunteer_date_invalid_format_rejected(
    sheets: MagicMock, cache: MagicMock
) -> None:
    group = build_group(sheets, cache)
    date_cmd = group.get_command("date")
    interaction = make_interaction()
    with patch("src.commands.volunteer.is_host", return_value=True):
        await date_cmd.callback(interaction, date="not-a-date", user=None)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_volunteer_date_past_date_rejected(
    sheets: MagicMock, cache: MagicMock
) -> None:
    group = build_group(sheets, cache)
    date_cmd = group.get_command("date")
    interaction = make_interaction()
    with (
        patch("src.commands.volunteer.is_host", return_value=True),
        patch("src.commands.volunteer.today_la", return_value=date(2025, 6, 10)),
    ):
        await date_cmd.callback(interaction, date="2025-06-09", user=None)
    interaction.response.send_message.assert_awaited_once()
    args, _ = interaction.response.send_message.call_args
    assert "past" in args[0].lower()


@pytest.mark.asyncio
async def test_volunteer_date_already_assigned_sends_error(
    sheets: MagicMock, cache: MagicMock
) -> None:
    ev = EventDate(date=date(2025, 6, 15), host_discord_id="99")
    cache.get_event.return_value = ev
    group = build_group(sheets, cache)
    date_cmd = group.get_command("date")
    interaction = make_interaction()
    with (
        patch("src.commands.volunteer.is_host", return_value=True),
        patch("src.commands.volunteer.today_la", return_value=date(2025, 6, 10)),
    ):
        await date_cmd.callback(interaction, date="2025-06-15", user=None)
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "already assigned" in args[0].lower() or "<@99>" in args[0]


@pytest.mark.asyncio
async def test_volunteer_date_happy_path(
    sheets: MagicMock, cache: MagicMock
) -> None:
    cache.get_event.return_value = None
    group = build_group(sheets, cache)
    date_cmd = group.get_command("date")
    interaction = make_interaction(user_id=1)
    with (
        patch("src.commands.volunteer.is_host", return_value=True),
        patch("src.commands.volunteer.today_la", return_value=date(2025, 6, 10)),
    ):
        await date_cmd.callback(interaction, date="2025-06-15", user=None)
    cache.upsert_event.assert_called_once()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "hosting" in args[0].lower() or "Jun 15" in args[0]


@pytest.mark.asyncio
async def test_volunteer_date_sheets_exception_sends_error(
    sheets: MagicMock, cache: MagicMock
) -> None:
    cache.get_event.return_value = None
    sheets.upsert_schedule_row.side_effect = RuntimeError("write failed")
    group = build_group(sheets, cache)
    date_cmd = group.get_command("date")
    interaction = make_interaction(user_id=1)
    with (
        patch("src.commands.volunteer.is_host", return_value=True),
        patch("src.commands.volunteer.today_la", return_value=date(2025, 6, 10)),
    ):
        await date_cmd.callback(interaction, date="2025-06-15", user=None)
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "Failed" in args[0] or "failed" in args[0]


# ── volunteer recurring ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_volunteer_recurring_non_host_rejected(
    sheets: MagicMock, cache: MagicMock
) -> None:
    group = build_group(sheets, cache)
    recurring_cmd = group.get_command("recurring")
    interaction = make_interaction()
    with patch("src.commands.volunteer.is_host", return_value=False):
        await recurring_cmd.callback(interaction, pattern="every monday", user=None)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_volunteer_recurring_invalid_pattern_rejected(
    sheets: MagicMock, cache: MagicMock
) -> None:
    group = build_group(sheets, cache)
    recurring_cmd = group.get_command("recurring")
    interaction = make_interaction()
    with patch("src.commands.volunteer.is_host", return_value=True):
        await recurring_cmd.callback(interaction, pattern="whenever I feel like it", user=None)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_volunteer_recurring_happy_path_shows_preview(
    sheets: MagicMock, cache: MagicMock
) -> None:
    cache.all_events.return_value = []
    group = build_group(sheets, cache)
    recurring_cmd = group.get_command("recurring")
    interaction = make_interaction()
    with (
        patch("src.commands.volunteer.is_host", return_value=True),
        patch("src.commands.volunteer.today_la", return_value=date(2025, 6, 1)),
    ):
        await recurring_cmd.callback(interaction, pattern="every monday", user=None)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert "view" in kwargs
    assert isinstance(kwargs["view"], _ConfirmView)


# ── _ConfirmView ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_confirm_view_wrong_invoker_rejected(
    sheets: MagicMock, cache: MagicMock
) -> None:
    invoker = MagicMock(spec=discord.Member)
    invoker.id = 1
    target = MagicMock(spec=discord.Member)
    target.id = 1
    target.display_name = "Host"
    parsed = ParsedPattern(kind="weekly", weekday=0)
    parsed.description = "every monday"
    view = _ConfirmView(sheets, cache, target, invoker, parsed, [date(2025, 6, 9)])
    interaction = make_interaction(user_id=2)
    btn = view.children[0]  # Confirm button
    await btn.callback(interaction)
    interaction.response.send_message.assert_awaited_once()
    args, _ = interaction.response.send_message.call_args
    assert "invoker" in args[0].lower() or "Only" in args[0]


@pytest.mark.asyncio
async def test_confirm_view_cancel_button(
    sheets: MagicMock, cache: MagicMock
) -> None:
    invoker = MagicMock(spec=discord.Member)
    invoker.id = 1
    target = MagicMock(spec=discord.Member)
    target.id = 1
    target.display_name = "Host"
    parsed = ParsedPattern(kind="weekly", weekday=0)
    parsed.description = "every monday"
    view = _ConfirmView(sheets, cache, target, invoker, parsed, [])
    interaction = make_interaction(user_id=1)
    cancel_btn = view.children[1]  # Cancel button
    await cancel_btn.callback(interaction)
    interaction.response.send_message.assert_awaited_once()
    args, _ = interaction.response.send_message.call_args
    assert "Cancelled" in args[0]
