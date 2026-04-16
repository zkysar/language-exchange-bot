"""Guards against drift between registered commands and /help text."""
from __future__ import annotations

from unittest.mock import MagicMock

import discord
from discord import app_commands

from src.commands import config_cmd as config_mod
from src.commands import help_cmd as help_mod
from src.commands import hosting as hosting_mod
from src.commands import schedule as schedule_mod
from src.commands import setup_wizard as setup_wizard_mod
from src.commands import sync as sync_mod

_UNDOCUMENTED_COMMANDS = {"help"}


def _build_tree() -> app_commands.CommandTree:
    sheets = MagicMock()
    cache = MagicMock()
    warnings = MagicMock()

    client = MagicMock()
    client._connection._command_tree = None
    tree = app_commands.CommandTree(client)
    tree.add_command(hosting_mod.build_command(sheets, cache, warnings))
    tree.add_command(schedule_mod.build_command(cache))
    tree.add_command(sync_mod.build_command(sheets, cache))
    tree.add_command(config_mod.build_group(sheets, cache))
    tree.add_command(setup_wizard_mod.build_command(sheets, cache))
    tree.add_command(help_mod.build_command(cache))
    return tree


def test_every_command_has_help_entry() -> None:
    tree = _build_tree()
    registered = {cmd.name for cmd in tree.get_commands()}
    registered -= _UNDOCUMENTED_COMMANDS

    documented = set(help_mod.COMMAND_HELP)

    missing = registered - documented
    extra = documented - registered
    assert not missing, f"commands missing COMMAND_HELP entries: {sorted(missing)}"
    assert not extra, f"COMMAND_HELP has stale entries: {sorted(extra)}"


def _mock_user(role_ids: list[int]) -> MagicMock:
    user = MagicMock(spec=discord.Member)
    user.id = 999
    user.roles = [MagicMock(id=rid) for rid in role_ids]
    return user


def _mock_config(
    member_ids=None, host_ids=None, admin_ids=None, owner_ids=None,
) -> MagicMock:
    config = MagicMock()
    config.member_role_ids = member_ids or []
    config.host_role_ids = host_ids or []
    config.admin_role_ids = admin_ids or []
    config.owner_user_ids = owner_ids or []
    return config


def test_autocomplete_filters_by_role() -> None:
    config = _mock_config(member_ids=[1], host_ids=[2], admin_ids=[3])

    member = _mock_user([1])
    visible = help_mod._visible_autocomplete(member, config)
    assert "schedule" in visible
    assert "hosting" not in visible
    assert "sync" not in visible

    host = _mock_user([2])
    visible = help_mod._visible_autocomplete(host, config)
    assert "schedule" in visible
    assert "hosting" in visible
    assert "sync" not in visible

    admin = _mock_user([3])
    visible = help_mod._visible_autocomplete(admin, config)
    assert "schedule" in visible
    assert "hosting" in visible
    assert "sync" in visible

    nobody = _mock_user([])
    visible = help_mod._visible_autocomplete(nobody, config)
    assert visible == []


def test_unconfigured_warning_in_embed() -> None:
    config = _mock_config()
    user = _mock_user([])
    embed = help_mod._build_embed(user, config)
    field_names = [f.name for f in embed.fields]
    assert "Not configured" in field_names


def test_no_warning_when_configured() -> None:
    config = _mock_config(member_ids=[1])
    user = _mock_user([1])
    embed = help_mod._build_embed(user, config)
    field_names = [f.name for f in embed.fields]
    assert "Not configured" not in field_names
    assert "View Schedule" in field_names
