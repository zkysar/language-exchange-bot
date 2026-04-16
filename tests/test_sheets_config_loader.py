from __future__ import annotations

from unittest.mock import MagicMock

from src.services.sheets_service import SheetsService


def _make_service_with_rows(rows: list[dict]) -> SheetsService:
    """Build a SheetsService instance with a fake worksheet returning `rows`."""
    svc = SheetsService.__new__(SheetsService)  # bypass __init__
    fake_ws = MagicMock()
    fake_ws.get_all_records.return_value = rows
    svc._get_or_create = MagicMock(return_value=fake_ws)  # type: ignore[attr-defined]
    return svc


def test_load_configuration_reads_announcement_channel_directly():
    svc = _make_service_with_rows([
        {"setting_key": "announcement_channel_id",
         "setting_value": "111", "setting_type": "string"},
    ])
    cfg = svc.load_configuration()
    assert cfg.announcement_channel_id == "111"


def test_load_configuration_falls_back_to_warnings_channel_id():
    svc = _make_service_with_rows([
        {"setting_key": "warnings_channel_id",
         "setting_value": "222", "setting_type": "string"},
    ])
    cfg = svc.load_configuration()
    assert cfg.announcement_channel_id == "222"


def test_load_configuration_falls_back_to_schedule_channel_id():
    svc = _make_service_with_rows([
        {"setting_key": "schedule_channel_id",
         "setting_value": "333", "setting_type": "string"},
    ])
    cfg = svc.load_configuration()
    assert cfg.announcement_channel_id == "333"


def test_load_configuration_prefers_announcement_over_legacy_keys():
    svc = _make_service_with_rows([
        {"setting_key": "schedule_channel_id",
         "setting_value": "333", "setting_type": "string"},
        {"setting_key": "warnings_channel_id",
         "setting_value": "222", "setting_type": "string"},
        {"setting_key": "announcement_channel_id",
         "setting_value": "111", "setting_type": "string"},
    ])
    cfg = svc.load_configuration()
    assert cfg.announcement_channel_id == "111"


def test_load_configuration_prefers_warnings_over_schedule_when_announcement_absent():
    svc = _make_service_with_rows([
        {"setting_key": "schedule_channel_id",
         "setting_value": "333", "setting_type": "string"},
        {"setting_key": "warnings_channel_id",
         "setting_value": "222", "setting_type": "string"},
    ])
    cfg = svc.load_configuration()
    assert cfg.announcement_channel_id == "222"


def test_load_configuration_none_when_no_channel_rows():
    svc = _make_service_with_rows([])
    cfg = svc.load_configuration()
    assert cfg.announcement_channel_id is None
