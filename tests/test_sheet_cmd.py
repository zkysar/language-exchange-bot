from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.commands.sheet import build_command, sheet_url


def test_sheet_url_with_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "abc123xyz")
    url = sheet_url()
    assert url == "https://docs.google.com/spreadsheets/d/abc123xyz/edit"


def test_sheet_url_missing_env_returns_url_with_empty_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_SHEETS_SPREADSHEET_ID", raising=False)
    url = sheet_url()
    assert url.startswith("https://docs.google.com/spreadsheets/d/")
    assert url.endswith("/edit")


@pytest.mark.asyncio
async def test_sheet_cmd_sends_url_in_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "sheet_id_xyz")
    cmd = build_command()
    interaction = MagicMock(spec=discord.Interaction)
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    await cmd.callback(interaction)
    interaction.response.send_message.assert_awaited_once()
    args, _ = interaction.response.send_message.call_args
    assert "sheet_id_xyz" in args[0]
