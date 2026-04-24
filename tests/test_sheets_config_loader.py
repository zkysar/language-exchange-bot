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


# ── nullable integer keys ─────────────────────────────────────────────────────

def test_load_configuration_empty_nullable_int_becomes_none():
    svc = _make_service_with_rows([
        {"setting_key": "warning_passive_days", "setting_value": "", "setting_type": "integer"},
        {"setting_key": "warning_urgent_days", "setting_value": "", "setting_type": "integer"},
        {"setting_key": "schedule_announcement_interval_days", "setting_value": "", "setting_type": "integer"},
        {"setting_key": "schedule_announcement_lookahead_weeks", "setting_value": "", "setting_type": "integer"},
    ])
    cfg = svc.load_configuration()
    assert cfg.warning_passive_days is None
    assert cfg.warning_urgent_days is None
    assert cfg.schedule_announcement_interval_days is None
    assert cfg.schedule_announcement_lookahead_weeks is None


def test_load_configuration_numeric_nullable_int_parses():
    svc = _make_service_with_rows([
        {"setting_key": "warning_passive_days", "setting_value": "7", "setting_type": "integer"},
        {"setting_key": "schedule_announcement_interval_days", "setting_value": "14", "setting_type": "integer"},
        {"setting_key": "schedule_announcement_lookahead_weeks", "setting_value": "6", "setting_type": "integer"},
    ])
    cfg = svc.load_configuration()
    assert cfg.warning_passive_days == 7
    assert cfg.schedule_announcement_interval_days == 14
    assert cfg.schedule_announcement_lookahead_weeks == 6


# ── last_schedule_announcement_at parsing ─────────────────────────────────────

def test_load_configuration_parses_tz_aware_last_schedule_announcement_at():
    svc = _make_service_with_rows([
        {"setting_key": "last_schedule_announcement_at",
         "setting_value": "2026-04-01T09:00:00+00:00", "setting_type": "string"},
    ])
    cfg = svc.load_configuration()
    assert cfg.last_schedule_announcement_at is not None
    assert cfg.last_schedule_announcement_at.tzinfo is not None


def test_load_configuration_rejects_tz_naive_last_schedule_announcement_at():
    svc = _make_service_with_rows([
        {"setting_key": "last_schedule_announcement_at",
         "setting_value": "2026-04-01T09:00:00", "setting_type": "string"},
    ])
    cfg = svc.load_configuration()
    assert cfg.last_schedule_announcement_at is None


def test_load_configuration_rejects_malformed_last_schedule_announcement_at():
    svc = _make_service_with_rows([
        {"setting_key": "last_schedule_announcement_at",
         "setting_value": "not-a-date", "setting_type": "string"},
    ])
    cfg = svc.load_configuration()
    assert cfg.last_schedule_announcement_at is None


def test_load_configuration_empty_last_schedule_announcement_at():
    svc = _make_service_with_rows([
        {"setting_key": "last_schedule_announcement_at",
         "setting_value": "", "setting_type": "string"},
    ])
    cfg = svc.load_configuration()
    assert cfg.last_schedule_announcement_at is None
