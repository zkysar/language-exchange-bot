"""Guards against drift between registered commands and /help text."""
from __future__ import annotations

from unittest.mock import MagicMock

import discord
from discord import app_commands

from src.commands import help_cmd as help_mod
from src.commands import reset as reset_mod
from src.commands import schedule as schedule_mod
from src.commands import sync as sync_mod
from src.commands import unvolunteer as unvolunteer_mod
from src.commands import volunteer as volunteer_mod
from src.commands import sheet as sheet_mod
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
    tree.add_command(warnings_mod.build_command(cache, warnings))
    tree.add_command(sync_mod.build_command(sheets, cache))
    tree.add_command(reset_mod.build_command(sheets, cache))
    tree.add_command(sheet_mod.build_command())
    tree.add_command(help_mod.build_command())
    return tree


def test_every_command_has_help_entry() -> None:
    tree = _build_tree()
    registered = {cmd.name for cmd in tree.get_commands()}
    registered.discard("help")

    documented = {k for k in help_mod.HELP_TEXT if k is not None}

    missing = registered - documented
    extra = documented - registered
    assert not missing, f"commands missing HELP_TEXT entries: {sorted(missing)}"
    assert not extra, f"HELP_TEXT has stale entries: {sorted(extra)}"


def test_choices_match_help_text() -> None:
    documented = {k for k in help_mod.HELP_TEXT if k is not None}
    choices = {c.value for c in help_mod._COMMAND_CHOICES}
    assert choices == documented
