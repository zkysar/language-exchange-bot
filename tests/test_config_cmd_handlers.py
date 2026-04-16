from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord import app_commands

from src.commands.config_cmd import build_command
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


def action_choice(value: str) -> str:
    return value


def key_choice(value: str, label: str | None = None) -> app_commands.Choice[str]:
    return app_commands.Choice(name=label or value, value=value)


@pytest.fixture
def sheets() -> MagicMock:
    return MagicMock()


@pytest.fixture
def cache() -> MagicMock:
    c = MagicMock()
    c.config = Configuration.default()
    c.refresh = AsyncMock()
    return c


# ── auth guard ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_non_owner_rejected(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=False):
        await cmd.callback(interaction, action=None, key=None, value=None)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True


# ── get (show all) ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_no_key_shows_all_settings(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction(guild=False)
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(interaction, action=None, key=None, value=None)
    args, _ = interaction.response.send_message.call_args
    text = args[0]
    assert "Passive warning days" in text
    assert "Urgent warning days" in text
    assert "Window weeks" in text
    assert "Daily check time" in text
    assert "Timezone" in text
    assert "Announcement channel" in text


@pytest.mark.asyncio
async def test_get_no_key_unset_channel_displays_not_set(
    sheets: MagicMock, cache: MagicMock
) -> None:
    cache.config.announcement_channel_id = None
    cmd = build_command(sheets, cache)
    interaction = make_interaction(guild=False)
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(interaction, action=None, key=None, value=None)
    args, _ = interaction.response.send_message.call_args
    assert "*not set*" in args[0]


@pytest.mark.asyncio
async def test_get_no_key_set_channel_displays_mention(
    sheets: MagicMock, cache: MagicMock
) -> None:
    cache.config.announcement_channel_id = "999888"
    cmd = build_command(sheets, cache)
    interaction = make_interaction(guild=False)
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(interaction, action=None, key=None, value=None)
    args, _ = interaction.response.send_message.call_args
    assert "<#999888>" in args[0]


@pytest.mark.asyncio
async def test_get_no_key_empty_roles_display_none(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    interaction.guild.get_role = MagicMock(return_value=None)
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(interaction, action=None, key=None, value=None)
    args, _ = interaction.response.send_message.call_args
    assert "*none*" in args[0]


@pytest.mark.asyncio
async def test_get_explicit_action_no_key_shows_all(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction(guild=False)
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(interaction, action=action_choice("get"), key=None, value=None)
    interaction.response.send_message.assert_awaited_once()
    args, _ = interaction.response.send_message.call_args
    assert "Passive warning days" in args[0]


# ── set (scalar settings) ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_valid_integer_writes_and_refreshes(
    sheets: MagicMock, cache: MagicMock
) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(
            interaction,
            action=action_choice("set"),
            key=key_choice("warning_passive_days", "Passive warning days"),
            value="5",
        )
    sheets.update_configuration.assert_called_once_with(
        "warning_passive_days", "5", type_="integer"
    )
    cache.refresh.assert_awaited_once_with(force=True)


@pytest.mark.asyncio
async def test_set_out_of_range_rejected(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(
            interaction,
            action=action_choice("set"),
            key=key_choice("warning_passive_days"),
            value="0",
        )
    sheets.update_configuration.assert_not_called()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "must be" in args[0] or "between" in args[0]


@pytest.mark.asyncio
async def test_set_valid_time_writes(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(
            interaction,
            action=action_choice("set"),
            key=key_choice("daily_check_time"),
            value="08:00",
        )
    sheets.update_configuration.assert_called_once_with(
        "daily_check_time", "08:00", type_="string"
    )


@pytest.mark.asyncio
async def test_set_invalid_time_rejected(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(
            interaction,
            action=action_choice("set"),
            key=key_choice("daily_check_time"),
            value="99:99",
        )
    sheets.update_configuration.assert_not_called()


@pytest.mark.asyncio
async def test_set_valid_timezone_writes(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(
            interaction,
            action=action_choice("set"),
            key=key_choice("daily_check_timezone"),
            value="America/New_York",
        )
    sheets.update_configuration.assert_called_once_with(
        "daily_check_timezone", "America/New_York", type_="string"
    )


@pytest.mark.asyncio
async def test_set_invalid_timezone_rejected(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(
            interaction,
            action=action_choice("set"),
            key=key_choice("daily_check_timezone"),
            value="Fake/Timezone",
        )
    sheets.update_configuration.assert_not_called()


@pytest.mark.asyncio
async def test_set_channel_with_mention_writes(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(
            interaction,
            action=action_choice("set"),
            key=key_choice("announcement_channel_id"),
            value="<#12345>",
        )
    sheets.update_configuration.assert_called_once_with(
        "announcement_channel_id", "12345", type_="string"
    )


@pytest.mark.asyncio
async def test_set_channel_invalid_value_rejected(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction(guild=False)
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(
            interaction,
            action=action_choice("set"),
            key=key_choice("announcement_channel_id"),
            value="not-a-channel",
        )
    sheets.update_configuration.assert_not_called()


@pytest.mark.asyncio
async def test_set_no_value_rejected(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(
            interaction,
            action=action_choice("set"),
            key=key_choice("warning_passive_days"),
            value=None,
        )
    sheets.update_configuration.assert_not_called()
    interaction.followup.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_role_bucket_key_rejected(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(
            interaction,
            action=action_choice("set"),
            key=key_choice("admin"),
            value="@SomeRole",
        )
    sheets.update_configuration.assert_not_called()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "add" in args[0].lower() or "remove" in args[0].lower()


# ── add (role buckets) ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_role_appends_and_persists(sheets: MagicMock, cache: MagicMock) -> None:
    cache.config.admin_role_ids = []
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(
            interaction,
            action=action_choice("add"),
            key=key_choice("admin"),
            value="<@&555>",
        )
    sheets.update_configuration.assert_called_once()
    call_args = sheets.update_configuration.call_args
    assert call_args[0][0] == "admin_role_ids"
    assert "555" in call_args[0][1]
    cache.refresh.assert_awaited_once_with(force=True)


@pytest.mark.asyncio
async def test_add_duplicate_role_is_no_op(sheets: MagicMock, cache: MagicMock) -> None:
    cache.config.admin_role_ids = [555]
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(
            interaction,
            action=action_choice("add"),
            key=key_choice("admin"),
            value="<@&555>",
        )
    sheets.update_configuration.assert_not_called()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "already" in args[0]


@pytest.mark.asyncio
async def test_add_scalar_key_rejected(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(
            interaction,
            action=action_choice("add"),
            key=key_choice("warning_passive_days"),
            value="5",
        )
    sheets.update_configuration.assert_not_called()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "set" in args[0].lower()


@pytest.mark.asyncio
async def test_add_no_value_rejected(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(
            interaction,
            action=action_choice("add"),
            key=key_choice("admin"),
            value=None,
        )
    sheets.update_configuration.assert_not_called()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "role" in args[0].lower()


@pytest.mark.asyncio
async def test_add_bare_role_id_works(sheets: MagicMock, cache: MagicMock) -> None:
    cache.config.host_role_ids = []
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(
            interaction,
            action=action_choice("add"),
            key=key_choice("host"),
            value="789",
        )
    sheets.update_configuration.assert_called_once()
    call_args = sheets.update_configuration.call_args
    assert "789" in call_args[0][1]


# ── remove (role buckets) ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_remove_existing_role(sheets: MagicMock, cache: MagicMock) -> None:
    cache.config.host_role_ids = [123, 456]
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(
            interaction,
            action=action_choice("remove"),
            key=key_choice("host"),
            value="<@&123>",
        )
    sheets.update_configuration.assert_called_once()
    call_args = sheets.update_configuration.call_args
    assert "123" not in call_args[0][1]
    assert "456" in call_args[0][1]


@pytest.mark.asyncio
async def test_remove_absent_role_is_no_op(sheets: MagicMock, cache: MagicMock) -> None:
    cache.config.host_role_ids = []
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(
            interaction,
            action=action_choice("remove"),
            key=key_choice("host"),
            value="<@&999>",
        )
    sheets.update_configuration.assert_not_called()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "not in" in args[0]


@pytest.mark.asyncio
async def test_remove_scalar_key_rejected(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(
            interaction,
            action=action_choice("remove"),
            key=key_choice("warning_passive_days"),
            value="5",
        )
    sheets.update_configuration.assert_not_called()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "set" in args[0].lower()


@pytest.mark.asyncio
async def test_remove_no_value_rejected(sheets: MagicMock, cache: MagicMock) -> None:
    cmd = build_command(sheets, cache)
    interaction = make_interaction()
    with patch("src.commands.config_cmd.is_owner", return_value=True):
        await cmd.callback(
            interaction,
            action=action_choice("remove"),
            key=key_choice("admin"),
            value=None,
        )
    sheets.update_configuration.assert_not_called()
    interaction.followup.send.assert_awaited_once()
    args, _ = interaction.followup.send.call_args
    assert "role" in args[0].lower()


# ── autocomplete ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_value_autocomplete_timezone_filters_by_prefix(
    sheets: MagicMock, cache: MagicMock
) -> None:
    cmd = build_command(sheets, cache)
    autocomplete_fn = cmd._params["value"].autocomplete
    interaction = make_interaction()
    interaction.namespace.key = "daily_check_timezone"
    results = await autocomplete_fn(interaction, "Pacific")
    assert len(results) <= 25
    assert all("pacific" in c.value.lower() for c in results)


@pytest.mark.asyncio
async def test_value_autocomplete_non_timezone_returns_empty(
    sheets: MagicMock, cache: MagicMock
) -> None:
    cmd = build_command(sheets, cache)
    autocomplete_fn = cmd._params["value"].autocomplete
    interaction = make_interaction()
    interaction.namespace.key = "warning_passive_days"
    results = await autocomplete_fn(interaction, "5")
    assert results == []
