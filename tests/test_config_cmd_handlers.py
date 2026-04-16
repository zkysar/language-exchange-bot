from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord import app_commands

from src.commands.config_cmd import build_group
from src.models.models import Configuration


def make_interaction(user_id: int = 1, guild: bool = True) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = user_id
    interaction.guild = MagicMock() if guild else None
    interaction.namespace = MagicMock()
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
    return c


# ── /config show ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_group_interaction_check_rejects_non_owner(
    sheets: MagicMock, cache: MagicMock
) -> None:
    group = build_group(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=False):
        result = await group.interaction_check(interaction)
    assert result is False
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_group_interaction_check_allows_owner(
    sheets: MagicMock, cache: MagicMock
) -> None:
    group = build_group(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        result = await group.interaction_check(interaction)
    assert result is True
    interaction.response.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_config_show_contains_all_fields(sheets: MagicMock, cache: MagicMock) -> None:
    group = build_group(sheets, cache)
    show = group.get_command("show")
    interaction = make_interaction(guild=False)
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await show.callback(interaction)
    args, _ = interaction.response.send_message.call_args
    text = args[0]
    assert "Passive warning days" in text
    assert "Urgent warning days" in text
    assert "Window weeks" in text
    assert "Daily check time" in text
    assert "Timezone" in text
    assert "Announcement channel" in text


@pytest.mark.asyncio
async def test_config_show_unset_channels_display_not_set(
    sheets: MagicMock, cache: MagicMock
) -> None:
    cache.config.announcement_channel_id = None
    group = build_group(sheets, cache)
    show = group.get_command("show")
    interaction = make_interaction(guild=False)
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await show.callback(interaction)
    args, _ = interaction.response.send_message.call_args
    assert "*not set*" in args[0]


@pytest.mark.asyncio
async def test_config_show_set_channel_displays_mention(
    sheets: MagicMock, cache: MagicMock
) -> None:
    cache.config.announcement_channel_id = "999888"
    group = build_group(sheets, cache)
    show = group.get_command("show")
    interaction = make_interaction(guild=False)
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await show.callback(interaction)
    args, _ = interaction.response.send_message.call_args
    assert "<#999888>" in args[0]


@pytest.mark.asyncio
async def test_config_show_empty_roles_display_none(sheets: MagicMock, cache: MagicMock) -> None:
    group = build_group(sheets, cache)
    show = group.get_command("show")
    interaction = make_interaction()
    interaction.guild.get_role = MagicMock(return_value=None)
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await show.callback(interaction)
    args, _ = interaction.response.send_message.call_args
    assert "*none*" in args[0]


# ── /config set ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_config_set_valid_integer_writes_and_refreshes(
    sheets: MagicMock, cache: MagicMock
) -> None:
    group = build_group(sheets, cache)
    set_cmd = group.get_command("set")
    interaction = make_interaction()
    setting = app_commands.Choice(name="Passive warning days", value="warning_passive_days")
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await set_cmd.callback(interaction, setting=setting, value="5")
    sheets.update_configuration.assert_called_once_with(
        "warning_passive_days", "5", type_="integer"
    )
    cache.refresh.assert_awaited_once_with(force=True)


@pytest.mark.asyncio
async def test_config_set_out_of_range_rejected(sheets: MagicMock, cache: MagicMock) -> None:
    group = build_group(sheets, cache)
    set_cmd = group.get_command("set")
    interaction = make_interaction()
    setting = app_commands.Choice(name="Passive warning days", value="warning_passive_days")
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await set_cmd.callback(interaction, setting=setting, value="0")  # min is 1
    sheets.update_configuration.assert_not_called()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "must be" in args[0] or "between" in args[0]


@pytest.mark.asyncio
async def test_config_set_valid_time_writes(sheets: MagicMock, cache: MagicMock) -> None:
    group = build_group(sheets, cache)
    set_cmd = group.get_command("set")
    interaction = make_interaction()
    setting = app_commands.Choice(name="Daily check time", value="daily_check_time")
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await set_cmd.callback(interaction, setting=setting, value="08:00")
    sheets.update_configuration.assert_called_once_with(
        "daily_check_time", "08:00", type_="string"
    )


@pytest.mark.asyncio
async def test_config_set_invalid_time_rejected(sheets: MagicMock, cache: MagicMock) -> None:
    group = build_group(sheets, cache)
    set_cmd = group.get_command("set")
    interaction = make_interaction()
    setting = app_commands.Choice(name="Daily check time", value="daily_check_time")
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await set_cmd.callback(interaction, setting=setting, value="99:99")
    sheets.update_configuration.assert_not_called()


@pytest.mark.asyncio
async def test_config_set_valid_timezone_writes(sheets: MagicMock, cache: MagicMock) -> None:
    group = build_group(sheets, cache)
    set_cmd = group.get_command("set")
    interaction = make_interaction()
    setting = app_commands.Choice(name="Timezone", value="daily_check_timezone")
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await set_cmd.callback(interaction, setting=setting, value="America/New_York")
    sheets.update_configuration.assert_called_once_with(
        "daily_check_timezone", "America/New_York", type_="string"
    )


@pytest.mark.asyncio
async def test_config_set_invalid_timezone_rejected(
    sheets: MagicMock, cache: MagicMock
) -> None:
    group = build_group(sheets, cache)
    set_cmd = group.get_command("set")
    interaction = make_interaction()
    setting = app_commands.Choice(name="Timezone", value="daily_check_timezone")
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await set_cmd.callback(interaction, setting=setting, value="Fake/Timezone")
    sheets.update_configuration.assert_not_called()


@pytest.mark.asyncio
async def test_config_set_channel_with_mention_writes(
    sheets: MagicMock, cache: MagicMock
) -> None:
    group = build_group(sheets, cache)
    set_cmd = group.get_command("set")
    interaction = make_interaction()
    setting = app_commands.Choice(name="Announcement channel", value="announcement_channel_id")
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await set_cmd.callback(interaction, setting=setting, value="<#12345>")
    sheets.update_configuration.assert_called_once_with(
        "announcement_channel_id", "12345", type_="string"
    )


@pytest.mark.asyncio
async def test_config_set_channel_invalid_value_rejected(
    sheets: MagicMock, cache: MagicMock
) -> None:
    group = build_group(sheets, cache)
    set_cmd = group.get_command("set")
    interaction = make_interaction(guild=False)
    setting = app_commands.Choice(name="Announcement channel", value="announcement_channel_id")
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await set_cmd.callback(interaction, setting=setting, value="not-a-channel")
    sheets.update_configuration.assert_not_called()


@pytest.mark.asyncio
async def test_value_autocomplete_timezone_filters_by_prefix(
    sheets: MagicMock, cache: MagicMock
) -> None:
    group = build_group(sheets, cache)
    set_cmd = group.get_command("set")
    autocomplete_fn = set_cmd._params["value"].autocomplete
    interaction = make_interaction()
    interaction.namespace.setting = "daily_check_timezone"
    results = await autocomplete_fn(interaction, "Pacific")
    assert len(results) <= 25
    assert all("pacific" in c.value.lower() for c in results)


@pytest.mark.asyncio
async def test_value_autocomplete_non_timezone_returns_empty(
    sheets: MagicMock, cache: MagicMock
) -> None:
    group = build_group(sheets, cache)
    set_cmd = group.get_command("set")
    autocomplete_fn = set_cmd._params["value"].autocomplete
    interaction = make_interaction()
    interaction.namespace.setting = "warning_passive_days"
    results = await autocomplete_fn(interaction, "5")
    assert results == []


# ── /config roles ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_roles_add_requires_role_parameter(sheets: MagicMock, cache: MagicMock) -> None:
    group = build_group(sheets, cache)
    roles_cmd = group.get_command("roles")
    interaction = make_interaction()
    action = app_commands.Choice(name="add", value="add")
    bucket = app_commands.Choice(name="admin", value="admin")
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await roles_cmd.callback(interaction, action=action, bucket=bucket, role=None)
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "role" in args[0].lower()


@pytest.mark.asyncio
async def test_roles_add_new_role_appends_and_persists(
    sheets: MagicMock, cache: MagicMock
) -> None:
    cache.config.admin_role_ids = []
    group = build_group(sheets, cache)
    roles_cmd = group.get_command("roles")
    interaction = make_interaction()
    action = app_commands.Choice(name="add", value="add")
    bucket = app_commands.Choice(name="admin", value="admin")
    role = MagicMock(spec=discord.Role)
    role.id = 555
    role.name = "Admins"
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await roles_cmd.callback(interaction, action=action, bucket=bucket, role=role)
    sheets.update_configuration.assert_called_once()
    call_args = sheets.update_configuration.call_args
    assert "admin_role_ids" in call_args[0][0]
    assert "555" in call_args[0][1]
    cache.refresh.assert_awaited_once_with(force=True)


@pytest.mark.asyncio
async def test_roles_add_duplicate_is_no_op(sheets: MagicMock, cache: MagicMock) -> None:
    cache.config.admin_role_ids = [555]
    group = build_group(sheets, cache)
    roles_cmd = group.get_command("roles")
    interaction = make_interaction()
    action = app_commands.Choice(name="add", value="add")
    bucket = app_commands.Choice(name="admin", value="admin")
    role = MagicMock(spec=discord.Role)
    role.id = 555
    role.name = "Admins"
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await roles_cmd.callback(interaction, action=action, bucket=bucket, role=role)
    sheets.update_configuration.assert_not_called()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "already" in args[0]


@pytest.mark.asyncio
async def test_roles_remove_existing_role(sheets: MagicMock, cache: MagicMock) -> None:
    cache.config.host_role_ids = [123, 456]
    group = build_group(sheets, cache)
    roles_cmd = group.get_command("roles")
    interaction = make_interaction()
    action = app_commands.Choice(name="remove", value="remove")
    bucket = app_commands.Choice(name="host", value="host")
    role = MagicMock(spec=discord.Role)
    role.id = 123
    role.name = "Hosts"
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await roles_cmd.callback(interaction, action=action, bucket=bucket, role=role)
    sheets.update_configuration.assert_called_once()
    call_args = sheets.update_configuration.call_args
    assert "123" not in call_args[0][1]
    assert "456" in call_args[0][1]


@pytest.mark.asyncio
async def test_roles_remove_absent_role_is_no_op(
    sheets: MagicMock, cache: MagicMock
) -> None:
    cache.config.host_role_ids = []
    group = build_group(sheets, cache)
    roles_cmd = group.get_command("roles")
    interaction = make_interaction()
    action = app_commands.Choice(name="remove", value="remove")
    bucket = app_commands.Choice(name="host", value="host")
    role = MagicMock(spec=discord.Role)
    role.id = 999
    role.name = "Ghost Role"
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await roles_cmd.callback(interaction, action=action, bucket=bucket, role=role)
    sheets.update_configuration.assert_not_called()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "not in" in args[0]


@pytest.mark.asyncio
async def test_roles_clear_writes_empty_list(sheets: MagicMock, cache: MagicMock) -> None:
    cache.config.member_role_ids = [1, 2, 3]
    group = build_group(sheets, cache)
    roles_cmd = group.get_command("roles")
    interaction = make_interaction()
    action = app_commands.Choice(name="clear", value="clear")
    bucket = app_commands.Choice(name="member", value="member")
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await roles_cmd.callback(interaction, action=action, bucket=bucket, role=None)
    sheets.update_configuration.assert_called_once()
    call_args = sheets.update_configuration.call_args
    assert call_args[0][1] == "[]"
