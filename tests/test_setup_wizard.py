from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import discord
import pytest
import pytest_asyncio

from src.commands.setup_wizard import (
    SetupWizardView,
    _ChannelSelectForSetting,
    _RoleSelectForBucket,
    build_command,
)


@pytest_asyncio.fixture
async def wizard(sheets, cache):
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = None
    view = SetupWizardView(sheets, cache, interaction)
    return view


def _make_interaction():
    interaction = MagicMock(spec=discord.Interaction)
    interaction.response = AsyncMock()
    return interaction


def test_setup_command_name(sheets, cache):
    cmd = build_command(sheets, cache)
    assert cmd.name == "setup"


def test_setup_command_description(sheets, cache):
    cmd = build_command(sheets, cache)
    assert "wizard" in cmd.description.lower() or "guided" in cmd.description.lower()


@pytest.mark.asyncio
async def test_role_select_callback_success(wizard, sheets, cache):
    select = _RoleSelectForBucket(wizard, "admin", placeholder="Select Admin roles...")
    role = MagicMock(spec=discord.Role)
    role.id = 123
    role.name = "organizer"

    with patch.object(type(select), "values", new_callable=PropertyMock, return_value=[role]):
        interaction = _make_interaction()
        await select.callback(interaction)

    sheets.update_configuration.assert_called_once_with("admin_role_ids", "[123]", type_="json")
    cache.refresh.assert_called_once_with(force=True)
    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args[0][0]
    assert "organizer" in msg


@pytest.mark.asyncio
async def test_role_select_callback_sheets_error(wizard, sheets, cache):
    sheets.update_configuration.side_effect = Exception("gspread timeout")
    select = _RoleSelectForBucket(wizard, "host", placeholder="Select Host roles...")
    role = MagicMock(spec=discord.Role)
    role.id = 456
    role.name = "host"

    with patch.object(type(select), "values", new_callable=PropertyMock, return_value=[role]):
        interaction = _make_interaction()
        await select.callback(interaction)

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args[0][0]
    assert "Failed" in msg
    cache.refresh.assert_not_called()


@pytest.mark.asyncio
async def test_channel_select_callback_success(wizard, sheets, cache):
    select = _ChannelSelectForSetting(wizard, "schedule_channel_id", placeholder="Select channel...")
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 789
    channel.mention = "<#789>"

    with patch.object(type(select), "values", new_callable=PropertyMock, return_value=[channel]):
        interaction = _make_interaction()
        await select.callback(interaction)

    sheets.update_configuration.assert_called_once_with("schedule_channel_id", "789", type_="string")
    cache.refresh.assert_called_once_with(force=True)
    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args[0][0]
    assert "<#789>" in msg


@pytest.mark.asyncio
async def test_channel_select_callback_sheets_error(wizard, sheets, cache):
    sheets.update_configuration.side_effect = Exception("auth error")
    select = _ChannelSelectForSetting(wizard, "warnings_channel_id", placeholder="Select channel...")
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 111
    channel.mention = "<#111>"

    with patch.object(type(select), "values", new_callable=PropertyMock, return_value=[channel]):
        interaction = _make_interaction()
        await select.callback(interaction)

    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args[0][0]
    assert "Failed" in msg
    cache.refresh.assert_not_called()


@pytest.mark.asyncio
async def test_channel_select_callback_no_selection(wizard, sheets, cache):
    select = _ChannelSelectForSetting(wizard, "schedule_channel_id", placeholder="Select channel...")

    with patch.object(type(select), "values", new_callable=PropertyMock, return_value=[]):
        interaction = _make_interaction()
        await select.callback(interaction)

    sheets.update_configuration.assert_not_called()
    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args[0][0]
    assert "No channel" in msg
