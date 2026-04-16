from __future__ import annotations

import pytest

from src.commands.sheet import sheet_url


def test_sheet_url_with_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "abc123xyz")
    url = sheet_url()
    assert url == "https://docs.google.com/spreadsheets/d/abc123xyz/edit"


def test_sheet_url_missing_env_returns_url_with_empty_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_SHEETS_SPREADSHEET_ID", raising=False)
    url = sheet_url()
    assert url.startswith("https://docs.google.com/spreadsheets/d/")
    assert url.endswith("/edit")
