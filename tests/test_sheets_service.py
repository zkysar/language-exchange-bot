from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import gspread

from src.models.models import AuditEntry, EventDate, RecurringPattern
from src.services.sheets_service import SheetsService


def _make_svc() -> SheetsService:
    """Construct SheetsService bypassing __init__ (which needs env/gspread auth)."""
    svc = SheetsService.__new__(SheetsService)
    svc.spreadsheet = MagicMock()
    svc.write_lock = asyncio.Lock()
    return svc


def _make_ws() -> MagicMock:
    ws = MagicMock(spec=gspread.Worksheet)
    ws.row_values.return_value = ["existing_header"]
    ws.get_all_values.return_value = []
    ws.get_all_records.return_value = []
    ws.col_values.return_value = []
    return ws


# ── _get_or_create ────────────────────────────────────────────────────────────

def test_get_or_create_existing_worksheet_with_headers_returned(
) -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.row_values.return_value = ["date", "host"]
    svc.spreadsheet.worksheet.return_value = ws
    result = svc._get_or_create("Schedule", ["date", "host"])
    assert result is ws
    ws.append_row.assert_not_called()


def test_get_or_create_existing_empty_worksheet_appends_headers() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.row_values.return_value = []  # empty
    svc.spreadsheet.worksheet.return_value = ws
    result = svc._get_or_create("Schedule", ["date", "host"])
    assert result is ws
    ws.append_row.assert_called_once_with(["date", "host"])


def test_get_or_create_missing_worksheet_creates_and_appends_headers() -> None:
    svc = _make_svc()
    new_ws = _make_ws()
    svc.spreadsheet.worksheet.side_effect = gspread.WorksheetNotFound
    svc.spreadsheet.add_worksheet.return_value = new_ws
    result = svc._get_or_create("NewSheet", ["col1", "col2"])
    svc.spreadsheet.add_worksheet.assert_called_once()
    new_ws.append_row.assert_called_once_with(["col1", "col2"])
    assert result is new_ws


# ── ensure_sheets ─────────────────────────────────────────────────────────────

def test_ensure_sheets_creates_all_four_sheets() -> None:
    svc = _make_svc()
    config_ws = _make_ws()
    config_ws.get_all_values.return_value = [["setting_key"]]  # header row only
    other_ws = _make_ws()
    other_ws.row_values.return_value = ["existing"]

    def ws_factory(title: str) -> MagicMock:
        if title == "Configuration":
            return config_ws
        return other_ws

    svc.spreadsheet.worksheet.side_effect = ws_factory
    with patch.object(svc, "apply_sheet_ux"):
        svc.ensure_sheets()
    # worksheet() should have been called for all four sheets
    titles = [c.args[0] for c in svc.spreadsheet.worksheet.call_args_list]
    assert "Schedule" in titles
    assert "RecurringPatterns" in titles
    assert "AuditLog" in titles
    assert "Configuration" in titles


def test_ensure_sheets_only_appends_missing_config_keys() -> None:
    svc = _make_svc()
    config_ws = _make_ws()
    # Simulate 2 existing keys
    config_ws.get_all_values.return_value = [
        ["setting_key"],  # header
        ["warning_passive_days", "4", "integer", "...", ""],
        ["warning_urgent_days", "1", "integer", "...", ""],
    ]
    other_ws = _make_ws()
    other_ws.row_values.return_value = ["existing"]

    svc.spreadsheet.worksheet.side_effect = lambda t: config_ws if t == "Configuration" else other_ws
    with patch.object(svc, "apply_sheet_ux"):
        svc.ensure_sheets()
    # append_row should only be called for the keys NOT already present
    appended_keys = [c.args[0][0] for c in config_ws.append_row.call_args_list]
    assert "warning_passive_days" not in appended_keys
    assert "warning_urgent_days" not in appended_keys
    # Other default keys should have been appended
    assert len(appended_keys) > 0


# ── load_configuration ────────────────────────────────────────────────────────

def test_load_configuration_integer_coercion() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.get_all_records.return_value = [
        {"setting_key": "warning_passive_days", "setting_value": "7", "setting_type": "integer"},
    ]
    svc.spreadsheet.worksheet.return_value = ws
    config = svc.load_configuration()
    assert config.warning_passive_days == 7


def test_load_configuration_json_array_coercion() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.get_all_records.return_value = [
        {"setting_key": "admin_role_ids", "setting_value": "[123, 456]", "setting_type": "json"},
    ]
    svc.spreadsheet.worksheet.return_value = ws
    config = svc.load_configuration()
    assert config.admin_role_ids == [123, 456]


def test_load_configuration_channel_id_none_when_empty() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.get_all_records.return_value = [
        {"setting_key": "schedule_channel_id", "setting_value": "", "setting_type": "string"},
    ]
    svc.spreadsheet.worksheet.return_value = ws
    config = svc.load_configuration()
    assert config.schedule_channel_id is None


def test_load_configuration_channel_id_set_when_present() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.get_all_records.return_value = [
        {"setting_key": "schedule_channel_id", "setting_value": "999", "setting_type": "string"},
    ]
    svc.spreadsheet.worksheet.return_value = ws
    config = svc.load_configuration()
    assert config.schedule_channel_id == "999"


def test_load_configuration_malformed_json_skipped() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.get_all_records.return_value = [
        {"setting_key": "admin_role_ids", "setting_value": "not-json", "setting_type": "json"},
    ]
    svc.spreadsheet.worksheet.return_value = ws
    # Should not raise; returns default
    config = svc.load_configuration()
    assert config.admin_role_ids == []


# ── update_configuration ──────────────────────────────────────────────────────

def test_update_configuration_existing_key_calls_update() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.get_all_values.return_value = [
        ["setting_key", "setting_value", "setting_type", "description", "updated_at"],
        ["warning_passive_days", "4", "integer", "desc", ""],
    ]
    svc.spreadsheet.worksheet.return_value = ws
    svc.update_configuration("warning_passive_days", "7", type_="integer")
    ws.update.assert_called_once()
    call_range = ws.update.call_args[0][0]
    assert "B2" in call_range


def test_update_configuration_missing_key_appends_row() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.get_all_values.return_value = [
        ["setting_key", "setting_value", "setting_type", "description", "updated_at"],
    ]
    svc.spreadsheet.worksheet.return_value = ws
    svc.update_configuration("new_key", "value", type_="string")
    ws.append_row.assert_called_once()
    appended = ws.append_row.call_args[0][0]
    assert appended[0] == "new_key"
    assert appended[1] == "value"


# ── load_schedule ─────────────────────────────────────────────────────────────

def test_load_schedule_valid_row_parsed() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.get_all_records.return_value = [
        {
            "date": "2025-06-10",
            "host_discord_id": "42",
            "host_username": "Alice",
            "recurring_pattern_id": "",
            "assigned_at": "",
            "assigned_by": "",
            "notes": "",
        }
    ]
    svc.spreadsheet.worksheet.return_value = ws
    events = svc.load_schedule()
    assert len(events) == 1
    assert events[0].date == date(2025, 6, 10)
    assert events[0].host_discord_id == "42"


def test_load_schedule_bad_date_row_skipped() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.get_all_records.return_value = [
        {"date": "not-a-date", "host_discord_id": "42", "host_username": "Alice"},
        {"date": "2025-06-11", "host_discord_id": "", "host_username": ""},
    ]
    svc.spreadsheet.worksheet.return_value = ws
    events = svc.load_schedule()
    assert len(events) == 1
    assert events[0].date == date(2025, 6, 11)


def test_load_schedule_bad_assigned_at_event_kept_with_none() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.get_all_records.return_value = [
        {
            "date": "2025-06-10",
            "host_discord_id": "42",
            "host_username": "Alice",
            "assigned_at": "bad-timestamp",
            "recurring_pattern_id": "",
            "assigned_by": "",
            "notes": "",
        }
    ]
    svc.spreadsheet.worksheet.return_value = ws
    events = svc.load_schedule()
    assert len(events) == 1
    assert events[0].assigned_at is None


# ── _find_schedule_row ────────────────────────────────────────────────────────

def test_find_schedule_row_returns_correct_index() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.col_values.return_value = ["date", "2025-06-09", "2025-06-10", "2025-06-11"]
    result = svc._find_schedule_row(ws, "2025-06-10")
    assert result == 3  # 1-based, skipping header


def test_find_schedule_row_returns_none_when_not_found() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.col_values.return_value = ["date", "2025-06-09"]
    result = svc._find_schedule_row(ws, "2025-06-15")
    assert result is None


# ── upsert_schedule_row ───────────────────────────────────────────────────────

def test_upsert_schedule_row_new_row_appends() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.col_values.return_value = ["date"]  # only header, target not found
    svc.spreadsheet.worksheet.return_value = ws
    event = EventDate(date=date(2025, 6, 10), host_discord_id="42", host_username="Alice")
    svc.upsert_schedule_row(event)
    ws.append_row.assert_called_once()
    row = ws.append_row.call_args[0][0]
    assert row[0] == "2025-06-10"
    assert row[1] == "42"


def test_upsert_schedule_row_existing_row_updates() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.col_values.return_value = ["date", "2025-06-10"]  # row 2
    svc.spreadsheet.worksheet.return_value = ws
    event = EventDate(date=date(2025, 6, 10), host_discord_id="99", host_username="Bob")
    svc.upsert_schedule_row(event)
    ws.update.assert_called_once()
    call_range = ws.update.call_args[0][0]
    assert "A2" in call_range


# ── clear_schedule_assignment ─────────────────────────────────────────────────

def test_clear_schedule_assignment_found_returns_true() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.col_values.return_value = ["date", "2025-06-10"]
    svc.spreadsheet.worksheet.return_value = ws
    result = svc.clear_schedule_assignment(date(2025, 6, 10))
    assert result is True
    ws.update.assert_called_once()


def test_clear_schedule_assignment_not_found_returns_false() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.col_values.return_value = ["date"]
    svc.spreadsheet.worksheet.return_value = ws
    result = svc.clear_schedule_assignment(date(2025, 6, 10))
    assert result is False
    ws.update.assert_not_called()


# ── delete_future_pattern_rows ────────────────────────────────────────────────

def test_delete_future_pattern_rows_clears_matching_future_rows() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.get_all_records.return_value = [
        {"recurring_pattern_id": "p1", "date": "2025-06-10"},
        {"recurring_pattern_id": "p1", "date": "2025-06-05"},  # before from_date
        {"recurring_pattern_id": "p2", "date": "2025-06-10"},  # different pattern
    ]
    svc.spreadsheet.worksheet.return_value = ws
    count = svc.delete_future_pattern_rows("p1", date(2025, 6, 8))
    assert count == 1
    ws.update.assert_called_once()


# ── load_patterns ─────────────────────────────────────────────────────────────

def test_load_patterns_active_true_parsed() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.get_all_records.return_value = [
        {
            "pattern_id": "p1",
            "host_discord_id": "42",
            "host_username": "Alice",
            "pattern_description": "every monday",
            "pattern_rule": "weekly:0",
            "start_date": "2025-06-02",
            "end_date": "",
            "is_active": "TRUE",
        }
    ]
    svc.spreadsheet.worksheet.return_value = ws
    patterns = svc.load_patterns()
    assert len(patterns) == 1
    assert patterns[0].is_active is True
    assert patterns[0].end_date is None


def test_load_patterns_active_false_parsed() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.get_all_records.return_value = [
        {
            "pattern_id": "p1",
            "host_discord_id": "42",
            "host_username": "Alice",
            "pattern_description": "every monday",
            "pattern_rule": "weekly:0",
            "start_date": "2025-06-02",
            "end_date": "",
            "is_active": "FALSE",
        }
    ]
    svc.spreadsheet.worksheet.return_value = ws
    patterns = svc.load_patterns()
    assert patterns[0].is_active is False


def test_load_patterns_bad_start_date_skips_row() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.get_all_records.return_value = [
        {
            "pattern_id": "p1",
            "host_discord_id": "42",
            "host_username": "Alice",
            "pattern_description": "every monday",
            "pattern_rule": "weekly:0",
            "start_date": "bad-date",
            "end_date": "",
            "is_active": "TRUE",
        }
    ]
    svc.spreadsheet.worksheet.return_value = ws
    patterns = svc.load_patterns()
    assert len(patterns) == 0


def test_load_patterns_end_date_parsed_when_present() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.get_all_records.return_value = [
        {
            "pattern_id": "p1",
            "host_discord_id": "42",
            "host_username": "Alice",
            "pattern_description": "every monday",
            "pattern_rule": "weekly:0",
            "start_date": "2025-06-02",
            "end_date": "2025-12-01",
            "is_active": "TRUE",
        }
    ]
    svc.spreadsheet.worksheet.return_value = ws
    patterns = svc.load_patterns()
    assert patterns[0].end_date == date(2025, 12, 1)


# ── append_pattern ────────────────────────────────────────────────────────────

def test_append_pattern_appends_row_in_correct_order() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.row_values.return_value = ["existing_header"]
    svc.spreadsheet.worksheet.return_value = ws
    pattern = RecurringPattern(
        pattern_id="p-abc",
        host_discord_id="42",
        host_username="Alice",
        pattern_description="every monday",
        pattern_rule="weekly:0",
        start_date=date(2025, 6, 2),
        is_active=True,
    )
    svc.append_pattern(pattern)
    ws.append_row.assert_called_once()
    row = ws.append_row.call_args[0][0]
    assert row[0] == "p-abc"
    assert row[1] == "42"
    assert row[2] == "Alice"
    assert row[3] == "every monday"
    assert row[5] == "2025-06-02"
    assert row[8] == "TRUE"


# ── deactivate_pattern ────────────────────────────────────────────────────────

def test_deactivate_pattern_found_updates_and_returns_true() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.col_values.return_value = ["pattern_id", "p-abc", "p-xyz"]
    ws.row_values.return_value = ["existing"]
    svc.spreadsheet.worksheet.return_value = ws
    result = svc.deactivate_pattern("p-abc")
    assert result is True
    ws.update.assert_called_once()
    call_range = ws.update.call_args[0][0]
    assert "I2" in call_range


def test_deactivate_pattern_not_found_returns_false() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.col_values.return_value = ["pattern_id", "other-pattern"]
    ws.row_values.return_value = ["existing"]
    svc.spreadsheet.worksheet.return_value = ws
    result = svc.deactivate_pattern("p-missing")
    assert result is False
    ws.update.assert_not_called()


# ── append_audit ──────────────────────────────────────────────────────────────

def test_append_audit_with_metadata() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.row_values.return_value = ["existing_header"]
    svc.spreadsheet.worksheet.return_value = ws
    entry = AuditEntry(
        entry_id="e1",
        timestamp=datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc),
        action_type="SYNC_FORCED",
        user_discord_id="42",
        metadata={"count": 5},
    )
    svc.append_audit(entry)
    ws.append_row.assert_called_once()
    row = ws.append_row.call_args[0][0]
    assert row[0] == "e1"
    assert row[2] == "SYNC_FORCED"
    assert row[3] == "42"
    assert row[9] == json.dumps({"count": 5})


def test_append_audit_empty_metadata_writes_empty_string() -> None:
    svc = _make_svc()
    ws = _make_ws()
    ws.row_values.return_value = ["existing_header"]
    svc.spreadsheet.worksheet.return_value = ws
    entry = AuditEntry(
        entry_id="e2",
        timestamp=datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc),
        action_type="VOLUNTEER",
        user_discord_id="42",
        metadata={},
    )
    svc.append_audit(entry)
    row = ws.append_row.call_args[0][0]
    assert row[9] == ""
