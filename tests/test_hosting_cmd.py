from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord import app_commands

from src.commands.hosting import _ConfirmView, _signup_date_autocomplete, build_command
from src.models.models import Configuration, EventDate, RecurringPattern
from src.services.warning_service import WarningItem
from tests.helpers import make_interaction


@pytest.fixture
def sheets() -> MagicMock:
    s = MagicMock()
    s.write_lock = asyncio.Lock()
    s.delete_future_pattern_rows = MagicMock(return_value=2)
    return s


@pytest.fixture
def warnings_svc() -> MagicMock:
    w = MagicMock()
    w.check = AsyncMock(return_value=[])
    return w


_SIGNUP = app_commands.Choice(name="signup", value="signup")
_CANCEL = app_commands.Choice(name="cancel", value="cancel")


# ── auth guards ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_hosting_non_host_rejected(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction()
    with patch("src.commands.hosting.is_host", return_value=False):
        await cmd.callback(interaction, action=_SIGNUP, date="2025-06-10")
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_hosting_non_admin_cannot_target_other_user(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction(user_id=1)
    other = MagicMock(spec=discord.User)
    other.id = 2
    other.display_name = "Victim"
    with (
        patch("src.commands.hosting.is_host", return_value=True),
        patch("src.commands.hosting.is_admin", return_value=False),
    ):
        await cmd.callback(interaction, action=_SIGNUP, date="2025-06-10", user=other)
    interaction.response.send_message.assert_awaited_once()
    args, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
    assert "admin" in args[0].lower()


@pytest.mark.asyncio
async def test_hosting_admin_can_target_other_user(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction(user_id=1)
    other = MagicMock(spec=discord.User)
    other.id = 2
    other.display_name = "Other"
    with (
        patch("src.commands.hosting.is_host", return_value=True),
        patch("src.commands.hosting.is_admin", return_value=True),
        patch("src.commands.hosting.today_la", return_value=date(2025, 6, 1)),
    ):
        await cmd.callback(interaction, action=_SIGNUP, date="2025-06-10", user=other)
    # Should NOT have hit the rejection path; defer is called when the real
    # signup flow runs.
    interaction.response.defer.assert_awaited()


@pytest.mark.asyncio
async def test_hosting_both_date_and_pattern_rejected(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction()
    with patch("src.commands.hosting.is_host", return_value=True):
        await cmd.callback(
            interaction, action=_SIGNUP, date="2025-06-10", pattern="every monday"
        )
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_hosting_neither_date_nor_pattern_rejected(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction()
    with patch("src.commands.hosting.is_host", return_value=True):
        await cmd.callback(interaction, action=_SIGNUP)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


# ── signup date ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_signup_date_invalid_format_rejected(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction()
    with patch("src.commands.hosting.is_host", return_value=True):
        await cmd.callback(interaction, action=_SIGNUP, date="bad-date")
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_signup_date_past_date_rejected(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction()
    with (
        patch("src.commands.hosting.is_host", return_value=True),
        patch("src.commands.hosting.today_la", return_value=date(2025, 6, 15)),
    ):
        await cmd.callback(interaction, action=_SIGNUP, date="2025-06-10")
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_signup_date_already_assigned_sends_error(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    ev = EventDate(date=date(2025, 6, 10), host_discord_id="99")
    cache.get_event.return_value = ev
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction(user_id=1)
    with (
        patch("src.commands.hosting.is_host", return_value=True),
        patch("src.commands.hosting.today_la", return_value=date(2025, 6, 1)),
    ):
        await cmd.callback(interaction, action=_SIGNUP, date="2025-06-10")
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "<@99>" in args[0] or "assigned" in args[0].lower()


@pytest.mark.asyncio
async def test_signup_date_happy_path(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cache.get_event.return_value = None
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction(user_id=1)
    with (
        patch("src.commands.hosting.is_host", return_value=True),
        patch("src.commands.hosting.today_la", return_value=date(2025, 6, 1)),
    ):
        await cmd.callback(interaction, action=_SIGNUP, date="2025-06-10")
    sheets.upsert_schedule_row.assert_called_once()
    cache.upsert_event.assert_called_once()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "hosting" in args[0].lower() or "<@1>" in args[0]


@pytest.mark.asyncio
async def test_signup_date_exception_sends_error(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cache.get_event.return_value = None
    sheets.upsert_schedule_row.side_effect = RuntimeError("sheet error")
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction(user_id=1)
    with (
        patch("src.commands.hosting.is_host", return_value=True),
        patch("src.commands.hosting.today_la", return_value=date(2025, 6, 1)),
    ):
        await cmd.callback(interaction, action=_SIGNUP, date="2025-06-10")
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "Failed" in args[0] or "error" in args[0].lower() or "sheet error" in args[0]


# ── signup recurring ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_signup_recurring_invalid_pattern_rejected(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction()
    with (
        patch("src.commands.hosting.is_host", return_value=True),
        patch(
            "src.commands.hosting.parse_pattern",
            side_effect=ValueError("bad pattern"),
        ),
    ):
        await cmd.callback(interaction, action=_SIGNUP, pattern="???")
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_signup_recurring_preview_sends_confirm_view(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    from src.utils.pattern_parser import ParsedPattern

    parsed = ParsedPattern(kind="weekly", weekday=0, nth=None, day_of_month=None)
    parsed.description = "every monday"
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction(user_id=1)
    with (
        patch("src.commands.hosting.is_host", return_value=True),
        patch("src.commands.hosting.parse_pattern", return_value=parsed),
        patch(
            "src.commands.hosting.generate_dates",
            return_value=[date(2025, 6, 9), date(2025, 6, 16)],
        ),
        patch("src.commands.hosting.today_la", return_value=date(2025, 6, 1)),
    ):
        await cmd.callback(interaction, action=_SIGNUP, pattern="every monday")
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert isinstance(kwargs.get("view"), _ConfirmView)


# ── _ConfirmView ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_confirm_view_wrong_invoker_rejected(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    invoker = MagicMock(spec=discord.Member)
    invoker.id = 1
    target = MagicMock(spec=discord.Member)
    target.id = 2
    target.display_name = "Target"
    from src.utils.pattern_parser import ParsedPattern

    parsed = ParsedPattern(kind="weekly", weekday=0, nth=None, day_of_month=None)
    parsed.description = "every monday"
    view = _ConfirmView(sheets, cache, target, invoker, parsed, [date(2025, 6, 9)])
    btn = view.children[0]  # Confirm button
    interaction = make_interaction(user_id=99)  # different user
    await btn.callback(interaction)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_confirm_view_cancel_button(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    invoker = MagicMock(spec=discord.Member)
    invoker.id = 1
    target = MagicMock(spec=discord.Member)
    target.id = 2
    target.display_name = "Target"
    from src.utils.pattern_parser import ParsedPattern

    parsed = ParsedPattern(kind="weekly", weekday=0, nth=None, day_of_month=None)
    parsed.description = "every monday"
    view = _ConfirmView(sheets, cache, target, invoker, parsed, [date(2025, 6, 9)])
    btn = view.children[1]  # Cancel button
    interaction = make_interaction(user_id=1)
    await btn.callback(interaction)
    interaction.response.send_message.assert_awaited_once()
    args, kwargs = interaction.response.send_message.call_args
    assert "Cancelled" in args[0]
    assert kwargs.get("ephemeral") is True


# ── cancel date ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cancel_date_invalid_date_rejected(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction()
    with patch("src.commands.hosting.is_host", return_value=True):
        await cmd.callback(interaction, action=_CANCEL, date="bad-date")
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_cancel_date_not_assigned_sends_error(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cache.get_event.return_value = None
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction()
    with patch("src.commands.hosting.is_host", return_value=True):
        await cmd.callback(interaction, action=_CANCEL, date="2025-06-10")
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "No one" in args[0] or "scheduled" in args[0].lower()


@pytest.mark.asyncio
async def test_cancel_date_wrong_user_sends_error(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    ev = EventDate(date=date(2025, 6, 10), host_discord_id="99")
    cache.get_event.return_value = ev
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction(user_id=1)
    with patch("src.commands.hosting.is_host", return_value=True):
        await cmd.callback(interaction, action=_CANCEL, date="2025-06-10")
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "<@1>" in args[0] or "not assigned" in args[0].lower()


@pytest.mark.asyncio
async def test_cancel_date_happy_path(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    ev = EventDate(date=date(2025, 6, 10), host_discord_id="1")
    cache.get_event.return_value = ev
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction(user_id=1)
    with patch("src.commands.hosting.is_host", return_value=True):
        await cmd.callback(interaction, action=_CANCEL, date="2025-06-10")
    cache.remove_event_assignment.assert_called_once()
    sheets.clear_schedule_assignment.assert_called_once()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "Removed" in args[0]


@pytest.mark.asyncio
async def test_cancel_date_appends_urgent_warning(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    target_date = date(2025, 6, 10)
    ev = EventDate(date=target_date, host_discord_id="1")
    cache.get_event.return_value = ev
    urgent_item = WarningItem(event_date=target_date, days_until=1, severity="urgent")
    warnings_svc.check.return_value = [urgent_item]
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction(user_id=1)
    with patch("src.commands.hosting.is_host", return_value=True):
        await cmd.callback(interaction, action=_CANCEL, date="2025-06-10")
    args, _ = interaction.followup.send.call_args
    assert "urgent" in args[0].lower() or "⚠️" in args[0]


# ── cancel recurring ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cancel_recurring_pattern_not_found_rejected(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cache.active_patterns_for.return_value = []
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction(user_id=1)
    with patch("src.commands.hosting.is_host", return_value=True):
        await cmd.callback(interaction, action=_CANCEL, pattern="p-999")
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_cancel_recurring_happy_path(
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
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction(user_id=1)
    with (
        patch("src.commands.hosting.is_host", return_value=True),
        patch("src.commands.hosting.today_la", return_value=date(2025, 6, 1)),
    ):
        await cmd.callback(interaction, action=_CANCEL, pattern="p-123")
    sheets.deactivate_pattern.assert_called_once_with("p-123")
    sheets.delete_future_pattern_rows.assert_called_once()
    cache.deactivate_pattern.assert_called_once_with("p-123")
    cache.invalidate.assert_called_once()
    cache.refresh.assert_awaited()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "Deactivated" in args[0]


# ── autocomplete ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_date_autocomplete_signup_returns_open_dates(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cache.all_events.return_value = []
    cmd = build_command(sheets, cache, warnings_svc)
    autocomplete = cmd._params["date"].autocomplete
    interaction = make_interaction()
    interaction.data = {"options": [{"name": "action", "value": "signup"}]}
    with patch("src.commands.hosting.today_la", return_value=date(2025, 6, 1)):
        results = await autocomplete(interaction, "")
    assert len(results) <= 25
    assert all(isinstance(c, app_commands.Choice) for c in results)


@pytest.mark.asyncio
async def test_date_autocomplete_cancel_returns_assigned_dates(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    events = [
        EventDate(date=date(2025, 6, 10), host_discord_id="1"),
        EventDate(date=date(2025, 5, 1), host_discord_id="1"),  # past — skipped
        EventDate(date=date(2025, 6, 11), host_discord_id="99"),  # different user
    ]
    cache.all_events.return_value = events
    cmd = build_command(sheets, cache, warnings_svc)
    autocomplete = cmd._params["date"].autocomplete
    interaction = make_interaction(user_id=1)
    interaction.data = {"options": [{"name": "action", "value": "cancel"}]}
    with patch("src.commands.hosting.today_la", return_value=date(2025, 6, 1)):
        results = await autocomplete(interaction, "")
    values = [c.value for c in results]
    assert "2025-06-10" in values
    assert "2025-05-01" not in values
    assert "2025-06-11" not in values


@pytest.mark.asyncio
async def test_pattern_autocomplete_signup_returns_suggestions(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cmd = build_command(sheets, cache, warnings_svc)
    autocomplete = cmd._params["pattern"].autocomplete
    interaction = make_interaction()
    interaction.data = {"options": [{"name": "action", "value": "signup"}]}
    results = await autocomplete(interaction, "")
    assert len(results) > 0
    values = [c.value for c in results]
    assert "every Tuesday" in values
    assert "every 2nd Tuesday" in values

    filtered = await autocomplete(interaction, "2nd")
    assert all("2nd" in c.name.lower() for c in filtered)


@pytest.mark.asyncio
async def test_pattern_autocomplete_cancel_returns_active_patterns(
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
    cmd = build_command(sheets, cache, warnings_svc)
    autocomplete = cmd._params["pattern"].autocomplete
    interaction = make_interaction(user_id=1)
    interaction.data = {"options": [{"name": "action", "value": "cancel"}]}
    results = await autocomplete(interaction, "")
    assert len(results) == 1
    assert results[0].value == "p-123"
    assert results[0].name == "every monday"


# ── signup date autocomplete with meeting_schedule ────────────────────────────

def _make_cache_for_autocomplete(meeting_schedule=None):
    cache = MagicMock()
    cache.config = Configuration.default()
    cache.config.meeting_schedule = meeting_schedule
    cache.refresh = AsyncMock()
    cache.all_events = MagicMock(return_value=[])
    return cache


@pytest.mark.asyncio
async def test_autocomplete_no_schedule_returns_all_days():
    cache = _make_cache_for_autocomplete(meeting_schedule=None)
    interaction = MagicMock(spec=discord.Interaction)
    choices = await _signup_date_autocomplete(interaction, "", cache)
    assert len(choices) == 25  # hits the cap


@pytest.mark.asyncio
async def test_autocomplete_with_wednesday_schedule_returns_only_wednesdays():
    cache = _make_cache_for_autocomplete(meeting_schedule="every wednesday")
    interaction = MagicMock(spec=discord.Interaction)
    choices = await _signup_date_autocomplete(interaction, "", cache)
    assert len(choices) > 0
    for choice in choices:
        d = date.fromisoformat(choice.value)
        assert d.weekday() == 2, f"{d} is not a Wednesday"


@pytest.mark.asyncio
async def test_autocomplete_with_invalid_schedule_falls_back_to_all_days():
    cache = _make_cache_for_autocomplete(meeting_schedule="not parseable garbage")
    interaction = MagicMock(spec=discord.Interaction)
    choices = await _signup_date_autocomplete(interaction, "", cache)
    assert len(choices) == 25  # graceful fallback


# ── single-date signup vs meeting_schedule ────────────────────────────────────

@pytest.mark.asyncio
async def test_signup_date_off_schedule_rejected(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    # meeting_schedule = every wednesday; host tries to sign up for Tuesday
    cache.config.meeting_schedule = "every wednesday"
    cache.get_event.return_value = None
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction(user_id=1)
    with (
        patch("src.commands.hosting.is_host", return_value=True),
        patch("src.commands.hosting.today_la", return_value=date(2026, 4, 1)),
    ):
        # 2026-04-14 is a Tuesday; meeting is every wednesday → blocked
        await cmd.callback(interaction, action=_SIGNUP, date="2026-04-14")
    sheets.upsert_schedule_row.assert_not_called()
    interaction.response.send_message.assert_awaited_once()
    args, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
    assert "meeting" in args[0].lower() or "schedule" in args[0].lower()


@pytest.mark.asyncio
async def test_signup_date_on_schedule_proceeds(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cache.config.meeting_schedule = "every wednesday"
    cache.get_event.return_value = None
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction(user_id=1)
    with (
        patch("src.commands.hosting.is_host", return_value=True),
        patch("src.commands.hosting.today_la", return_value=date(2026, 4, 1)),
    ):
        # 2026-04-15 is a Wednesday → allowed
        await cmd.callback(interaction, action=_SIGNUP, date="2026-04-15")
    sheets.upsert_schedule_row.assert_called_once()


@pytest.mark.asyncio
async def test_signup_date_unset_schedule_allows_any_day(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cache.config.meeting_schedule = None  # unset — any day allowed
    cache.get_event.return_value = None
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction(user_id=1)
    with (
        patch("src.commands.hosting.is_host", return_value=True),
        patch("src.commands.hosting.today_la", return_value=date(2026, 4, 1)),
    ):
        await cmd.callback(interaction, action=_SIGNUP, date="2026-04-14")
    sheets.upsert_schedule_row.assert_called_once()


# ── recurring signup vs meeting_schedule ──────────────────────────────────────

@pytest.mark.asyncio
async def test_signup_recurring_misaligned_blocked(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cache.config.meeting_schedule = "every wednesday"
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction(user_id=1)
    with (
        patch("src.commands.hosting.is_host", return_value=True),
        patch("src.commands.hosting.today_la", return_value=date(2026, 4, 1)),
    ):
        await cmd.callback(interaction, action=_SIGNUP, pattern="every tuesday")
    interaction.response.send_message.assert_awaited_once()
    args, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
    # Error should mention the meeting schedule
    assert "every wednesday" in args[0].lower() or "meeting" in args[0].lower()


@pytest.mark.asyncio
async def test_signup_recurring_aligned_proceeds_to_preview(
    sheets: MagicMock, cache: MagicMock, warnings_svc: MagicMock
) -> None:
    cache.config.meeting_schedule = "every wednesday"
    cmd = build_command(sheets, cache, warnings_svc)
    interaction = make_interaction(user_id=1)
    with (
        patch("src.commands.hosting.is_host", return_value=True),
        patch("src.commands.hosting.today_la", return_value=date(2026, 4, 1)),
    ):
        # "every wednesday" matches the meeting schedule exactly
        await cmd.callback(
            interaction, action=_SIGNUP, pattern="every wednesday"
        )
    # Non-blocked path sends a preview message with a confirmation view
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert isinstance(kwargs.get("view"), _ConfirmView)
