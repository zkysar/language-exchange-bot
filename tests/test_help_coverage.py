"""Guards against drift between registered commands and /help text."""
from __future__ import annotations

from unittest.mock import MagicMock

import discord
from discord import app_commands

from src.commands import help_cmd as help_mod
from src.commands import listdates as listdates_mod
from src.commands import reset as reset_mod
from src.commands import schedule as schedule_mod
from src.commands import setup as setup_mod
from src.commands import sheet as sheet_mod
from src.commands import sync as sync_mod
from src.commands import unvolunteer as unvolunteer_mod
from src.commands import volunteer as volunteer_mod
from src.commands import warnings_cmd as warnings_mod


def _build_tree() -> app_commands.CommandTree:
    sheets = MagicMock()
    cache = MagicMock()
    warnings = MagicMock()

    client = MagicMock()
    client._connection._command_tree = None
    tree = app_commands.CommandTree(client)
    tree.add_command(volunteer_mod.build_group(sheets, cache))
    tree.add_command(unvolunteer_mod.build_group(sheets, cache, warnings))
    tree.add_command(schedule_mod.build_command(cache))
    tree.add_command(listdates_mod.build_command(cache))
    tree.add_command(warnings_mod.build_command(cache, warnings))
    tree.add_command(sync_mod.build_command(sheets, cache))
    tree.add_command(reset_mod.build_command(sheets, cache))
    tree.add_command(setup_mod.build_group(sheets, cache))
    tree.add_command(sheet_mod.build_command())
    tree.add_command(help_mod.build_command(cache))
    return tree


def _all_tiered_names() -> set[str]:
    names: set[str] = set()
    for _, entries in help_mod.TIERED_COMMANDS:
        for name, _ in entries:
            names.add(name)
    return names


def test_every_command_has_help_entry() -> None:
    tree = _build_tree()
    registered = {cmd.name for cmd in tree.get_commands()}
    registered.discard("help")

    documented = set(help_mod.COMMAND_DETAIL.keys())

    missing = registered - documented
    extra = documented - registered
    assert not missing, f"commands missing COMMAND_DETAIL entries: {sorted(missing)}"
    assert not extra, f"COMMAND_DETAIL has stale entries: {sorted(extra)}"


def test_detail_keys_covered_by_tiers() -> None:
    """Every COMMAND_DETAIL entry should appear in TIERED_COMMANDS (excluding help)."""
    tiered = _all_tiered_names()
    detail = set(help_mod.COMMAND_DETAIL.keys())
    missing = detail - tiered
    assert not missing, f"COMMAND_DETAIL entries not in TIERED_COMMANDS: {sorted(missing)}"


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


def test_visible_commands_filters_by_role() -> None:
    config = _mock_config(member_ids=[1], host_ids=[2], admin_ids=[3])

    member = _mock_user([1])
    _, visible = help_mod._visible_commands(member, config)
    assert "schedule" in visible
    assert "volunteer" not in visible
    assert "sync" not in visible

    host = _mock_user([2])
    _, visible = help_mod._visible_commands(host, config)
    assert "schedule" in visible
    assert "volunteer" in visible
    assert "sync" not in visible

    admin = _mock_user([3])
    _, visible = help_mod._visible_commands(admin, config)
    assert "schedule" in visible
    assert "volunteer" in visible
    assert "sync" in visible

    everyone_sees = {"help", "sheet"}
    nobody = _mock_user([])
    _, visible = help_mod._visible_commands(nobody, config)
    assert set(visible) == everyone_sees


def test_unconfigured_warning_shown() -> None:
    config = _mock_config()
    user = _mock_user([])
    text = help_mod._build_overview(user, config)
    assert "No roles are configured yet" in text


def test_no_warning_when_configured() -> None:
    config = _mock_config(member_ids=[1])
    user = _mock_user([1])
    text = help_mod._build_overview(user, config)
    assert "No roles are configured yet" not in text
