from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.commands.setup_wizard import (
    SetupWizardView,
    _ChannelSelectForSetting,
    _DoneButton,
    _MeetingPatternModal,
    _NextButton,
    _RoleSelectForBucket,
    _ScheduleModal,
    build_command,
)
from src.models.models import Configuration


def make_interaction(user_id: int = 1, guild: bool = True) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = user_id
    interaction.guild = MagicMock() if guild else None
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
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
    return c


# ── build_command ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_setup_non_owner_rejected(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.setup_wizard.is_owner", return_value=False):
        await cmd.callback(interaction)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_setup_dm_rejected(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction(guild=False)
    with patch("src.commands.setup_wizard.is_owner", return_value=True):
        await cmd.callback(interaction)
    interaction.response.send_message.assert_awaited_once()
    args, kwargs = interaction.response.send_message.call_args
    assert "server" in args[0].lower()
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_setup_happy_path_sends_embed_with_view(
    sheets: MagicMock, cache: MagicMock
) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.setup_wizard.is_owner", return_value=True):
        await cmd.callback(interaction)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert "embed" in kwargs
    assert "view" in kwargs
    assert isinstance(kwargs["view"], SetupWizardView)
    assert kwargs.get("ephemeral") is True


# ── SetupWizardView step navigation ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_next_button_increments_step(sheets: MagicMock, cache: MagicMock) -> None:
    orig_interaction = make_interaction()
    view = SetupWizardView(sheets, cache, orig_interaction)
    assert view.step == 0
    btn = _NextButton(view)
    interaction = make_interaction()
    await btn.callback(interaction)
    assert view.step == 1
    interaction.response.edit_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_next_button_advances_through_all_steps(
    sheets: MagicMock, cache: MagicMock
) -> None:
    orig_interaction = make_interaction()
    view = SetupWizardView(sheets, cache, orig_interaction)
    for expected_step in [1, 2, 3]:
        btn = _NextButton(view)
        interaction = make_interaction()
        await btn.callback(interaction)
        assert view.step == expected_step


@pytest.mark.asyncio
async def test_done_button_stops_view(sheets: MagicMock, cache: MagicMock) -> None:
    orig_interaction = make_interaction()
    view = SetupWizardView(sheets, cache, orig_interaction)
    btn = _DoneButton(view)
    interaction = make_interaction()
    await btn.callback(interaction)
    interaction.response.edit_message.assert_awaited_once()
    _, kwargs = interaction.response.edit_message.call_args
    embed = kwargs.get("embed")
    assert embed is not None
    assert "complete" in embed.title.lower()


# ── _RoleSelectForBucket ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_role_select_writes_ids_and_refreshes(
    sheets: MagicMock, cache: MagicMock
) -> None:
    orig_interaction = make_interaction()
    view = SetupWizardView(sheets, cache, orig_interaction)
    select = _RoleSelectForBucket(view, "admin", placeholder="Select admin roles...")
    # Simulate 2 roles selected
    role_a = MagicMock(spec=discord.Role)
    role_a.id = 111
    role_a.name = "Admins"
    role_b = MagicMock(spec=discord.Role)
    role_b.id = 222
    role_b.name = "Mods"
    select._values = [role_a, role_b]
    interaction = make_interaction()
    await select.callback(interaction)
    sheets.update_configuration.assert_called_once()
    call_args = sheets.update_configuration.call_args
    assert call_args[0][0] == "admin_role_ids"
    assert "111" in call_args[0][1] and "222" in call_args[0][1]
    cache.refresh.assert_awaited_once_with(force=True)


@pytest.mark.asyncio
async def test_role_select_empty_values_clears(sheets: MagicMock, cache: MagicMock) -> None:
    orig_interaction = make_interaction()
    view = SetupWizardView(sheets, cache, orig_interaction)
    select = _RoleSelectForBucket(view, "host", placeholder="Select host roles...")
    select._values = []
    interaction = make_interaction()
    await select.callback(interaction)
    sheets.update_configuration.assert_called_once()
    call_args = sheets.update_configuration.call_args
    assert call_args[0][1] == "[]"


# ── _ChannelSelectForSetting ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_channel_select_with_channel_writes_id(
    sheets: MagicMock, cache: MagicMock
) -> None:
    orig_interaction = make_interaction()
    view = SetupWizardView(sheets, cache, orig_interaction)
    select = _ChannelSelectForSetting(view, "schedule_channel_id", placeholder="Select channel...")
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 999
    channel.mention = "<#999>"
    select._values = [channel]
    interaction = make_interaction()
    await select.callback(interaction)
    sheets.update_configuration.assert_called_once_with(
        "schedule_channel_id", "999", type_="string"
    )
    cache.refresh.assert_awaited_once_with(force=True)


@pytest.mark.asyncio
async def test_channel_select_no_channel_sends_message(
    sheets: MagicMock, cache: MagicMock
) -> None:
    orig_interaction = make_interaction()
    view = SetupWizardView(sheets, cache, orig_interaction)
    select = _ChannelSelectForSetting(view, "warnings_channel_id", placeholder="Select channel...")
    select._values = []
    interaction = make_interaction()
    await select.callback(interaction)
    sheets.update_configuration.assert_not_called()
    interaction.response.send_message.assert_awaited_once()


# ── _ScheduleModal ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_schedule_modal_valid_fields_writes_all(
    sheets: MagicMock, cache: MagicMock
) -> None:
    orig_interaction = make_interaction()
    view = SetupWizardView(sheets, cache, orig_interaction)
    modal = _ScheduleModal(view)
    modal.check_time._value = "09:00"
    modal.timezone._value = "America/Los_Angeles"
    modal.passive_days._value = "5"
    modal.urgent_days._value = "2"
    modal.window_weeks._value = "4"
    interaction = make_interaction()
    await modal.on_submit(interaction)
    assert sheets.update_configuration.call_count == 5
    cache.refresh.assert_awaited_once_with(force=True)
    assert view.step == 3


@pytest.mark.asyncio
async def test_schedule_modal_invalid_field_sends_errors_no_write(
    sheets: MagicMock, cache: MagicMock
) -> None:
    orig_interaction = make_interaction()
    view = SetupWizardView(sheets, cache, orig_interaction)
    modal = _ScheduleModal(view)
    modal.check_time._value = "25:00"  # invalid
    modal.timezone._value = "America/Los_Angeles"
    modal.passive_days._value = "5"
    modal.urgent_days._value = "2"
    modal.window_weeks._value = "4"
    interaction = make_interaction()
    await modal.on_submit(interaction)
    interaction.response.send_message.assert_awaited_once()
    args, _ = interaction.response.send_message.call_args
    assert "Validation errors" in args[0] or "error" in args[0].lower()
    sheets.update_configuration.assert_not_called()


@pytest.mark.asyncio
async def test_schedule_modal_multiple_errors_collected(
    sheets: MagicMock, cache: MagicMock
) -> None:
    orig_interaction = make_interaction()
    view = SetupWizardView(sheets, cache, orig_interaction)
    modal = _ScheduleModal(view)
    modal.check_time._value = "bad"
    modal.timezone._value = "Not/ATimezone"
    modal.passive_days._value = "99"  # out of range
    modal.urgent_days._value = "2"
    modal.window_weeks._value = "4"
    interaction = make_interaction()
    await modal.on_submit(interaction)
    args, _ = interaction.response.send_message.call_args
    # Multiple errors should be listed
    assert args[0].count("-") >= 2 or args[0].count("\n") >= 2
    sheets.update_configuration.assert_not_called()


# ── _MeetingPatternModal ──────────────────────────────────────────────────────

def test_meeting_pattern_modal_exists() -> None:
    assert issubclass(_MeetingPatternModal, discord.ui.Modal)


@pytest.mark.asyncio
async def test_step3_embed_shows_meeting_pattern(sheets: MagicMock, cache: MagicMock) -> None:
    orig_interaction = make_interaction()
    view = SetupWizardView(sheets, cache, orig_interaction)
    view.cache.config.meeting_pattern = "every wednesday"
    embed = view._build_schedule_embed()
    field_values = [f.value for f in embed.fields]
    assert any("every wednesday" in v for v in field_values)


@pytest.mark.asyncio
async def test_step3_embed_shows_not_set_when_no_pattern(sheets: MagicMock, cache: MagicMock) -> None:
    orig_interaction = make_interaction()
    view = SetupWizardView(sheets, cache, orig_interaction)
    view.cache.config.meeting_pattern = None
    embed = view._build_schedule_embed()
    field_values = [f.value for f in embed.fields]
    assert any("not set" in v.lower() for v in field_values)


@pytest.mark.asyncio
async def test_meeting_pattern_modal_valid_pattern_writes_and_refreshes(
    sheets: MagicMock, cache: MagicMock
) -> None:
    orig_interaction = make_interaction()
    view = SetupWizardView(sheets, cache, orig_interaction)
    modal = _MeetingPatternModal(view)
    modal.pattern._value = "every wednesday"
    interaction = make_interaction()
    await modal.on_submit(interaction)
    sheets.update_configuration.assert_called_once_with(
        "meeting_pattern", "every wednesday", type_="string"
    )
    cache.refresh.assert_awaited_once_with(force=True)


@pytest.mark.asyncio
async def test_meeting_pattern_modal_empty_pattern_clears(
    sheets: MagicMock, cache: MagicMock
) -> None:
    orig_interaction = make_interaction()
    view = SetupWizardView(sheets, cache, orig_interaction)
    modal = _MeetingPatternModal(view)
    modal.pattern._value = ""
    interaction = make_interaction()
    await modal.on_submit(interaction)
    sheets.update_configuration.assert_called_once_with(
        "meeting_pattern", "", type_="string"
    )
    cache.refresh.assert_awaited_once_with(force=True)
