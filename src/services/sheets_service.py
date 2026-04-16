from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import gspread
from google.oauth2.service_account import Credentials

from src.models.models import (
    AuditEntry,
    Configuration,
    EventDate,
    RecurringPattern,
)
from src.utils.date_parser import format_date, parse_iso_date
from src.utils.logger import get_logger

log = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def _escape_cell(value: str) -> str:
    """Prefix `'` to neutralize Sheets formula injection from user-influenced text."""
    if not value:
        return value
    if value[0] in _FORMULA_PREFIXES:
        return "'" + value
    return value

SCHEDULE_HEADERS = [
    "date", "host_discord_id", "host_username", "recurring_pattern_id",
    "assigned_at", "assigned_by", "notes",
]
SCHEDULE_DISPLAY_HEADERS = ["Date", "Host ID", "Host", "", "", "", "Notes"]

INSTRUCTIONS_CONTENT = [
    "Language Exchange Bot - Schedule Sheet",
    "",
    "This spreadsheet is managed by the Discord bot. Here's what you need to know:",
    "",
    "SCHEDULE TAB (safe to edit):",
    '- Date: Event dates in YYYY-MM-DD format',
    '- Host: The Discord username of the person hosting',
    '- Notes: Any notes about the event (optional)',
    '- Blank host = unassigned date (the bot will send reminders)',
    "",
    "WHAT NOT TO DO:",
    '- Don\'t edit the "Host ID" column \u2014 the bot fills this from Discord',
    '- Don\'t rename or reorder columns',
    '- Don\'t touch hidden sheets (RecurringPatterns, AuditLog, Configuration)',
    '  unless you know what you\'re doing',
    "",
    "NEED HELP?",
    '- Use /help in Discord for bot commands',
    '- Use /schedule to see upcoming dates',
    '- Use /volunteer to sign up for a date',
]
PATTERN_HEADERS = [
    "pattern_id", "host_discord_id", "host_username", "pattern_description",
    "pattern_rule", "start_date", "end_date", "created_at", "is_active",
]
AUDIT_HEADERS = [
    "entry_id", "timestamp", "action_type", "user_discord_id",
    "target_user_discord_id", "event_date", "recurring_pattern_id",
    "outcome", "error_message", "metadata",
]
CONFIG_HEADERS = ["setting_key", "setting_value", "setting_type", "description", "updated_at"]

DEFAULT_CONFIG_ROWS = [
    ("warning_passive_days", "4", "integer", "Days before event to post passive warning"),
    ("warning_urgent_days", "1", "integer", "Days before event to post urgent warning"),
    ("daily_check_time", "09:00", "string", "Time of day for daily warning check (HH:MM)"),
    ("daily_check_timezone", "America/Los_Angeles", "string", "IANA timezone"),
    ("schedule_window_weeks", "2", "integer", "Default weeks shown in /schedule"),
    ("host_role_ids", "[]", "json", "Discord role IDs for hosts"),
    ("admin_role_ids", "[]", "json", "Discord role IDs for admins"),
    ("owner_user_ids", "[166793917461692416]", "json", "Discord user IDs with full bot access (owner/setup)"),
    ("announcement_channel_id", "", "string", "Discord channel ID where the bot posts schedule announcements and host-needed warnings"),
    ("cache_ttl_seconds", "300", "integer", "Cache TTL in seconds"),
    ("max_batch_size", "100", "integer", "Max rows per batch write"),
]


class SheetsService:
    def __init__(self) -> None:
        self.spreadsheet_id = os.environ["GOOGLE_SHEETS_SPREADSHEET_ID"]
        creds_file = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_FILE")
        creds_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
        if creds_json:
            info = json.loads(creds_json)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        elif creds_file:
            creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
        else:
            raise RuntimeError(
                "Set GOOGLE_SHEETS_CREDENTIALS_FILE or GOOGLE_SHEETS_CREDENTIALS"
            )
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
        self.write_lock = asyncio.Lock()

    # -- sheet helpers --
    def _get_or_create(self, title: str, headers: List[str]) -> gspread.Worksheet:
        try:
            ws = self.spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title=title, rows=1000, cols=max(10, len(headers)))
            ws.append_row(headers)
            return ws
        existing = ws.row_values(1)
        if not existing:
            ws.append_row(headers)
        return ws

    def ensure_sheets(self) -> None:
        self._get_or_create("Schedule", SCHEDULE_HEADERS)
        self._get_or_create("RecurringPatterns", PATTERN_HEADERS)
        self._get_or_create("AuditLog", AUDIT_HEADERS)
        config_ws = self._get_or_create("Configuration", CONFIG_HEADERS)
        existing_keys = {r[0] for r in config_ws.get_all_values()[1:] if r}
        for key, value, type_, desc in DEFAULT_CONFIG_ROWS:
            if key not in existing_keys:
                config_ws.append_row([key, value, type_, desc, datetime.now(timezone.utc).isoformat()])
        try:
            self.apply_sheet_ux()
        except Exception:
            log.warning("sheet UX setup failed (non-fatal)", exc_info=True)

    # -- sheet UX --
    def apply_sheet_ux(self) -> None:
        schedule_ws = self.spreadsheet.worksheet("Schedule")
        self._setup_instructions_tab()
        self._setup_schedule_display_row(schedule_ws)
        self._hide_internal_tabs()
        self._protect_internal_tabs()
        self._apply_schedule_formatting(schedule_ws)
        log.info("sheet UX applied")

    def _setup_instructions_tab(self) -> None:
        try:
            ws = self.spreadsheet.worksheet("Instructions")
        except gspread.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(
                title="Instructions", rows=25, cols=1,
            )
        ws.update(
            f"A1:A{len(INSTRUCTIONS_CONTENT)}",
            [[line] for line in INSTRUCTIONS_CONTENT],
        )
        ws.format("A1", {
            "textFormat": {"bold": True, "fontSize": 14},
        })
        ws.format("A5", {"textFormat": {"bold": True}})
        ws.format("A11", {"textFormat": {"bold": True}})
        ws.format("A17", {"textFormat": {"bold": True}})
        ws.freeze(rows=1)
        self._protect_sheet_if_needed(ws, warning_only=False)
        all_sheets = self.spreadsheet.worksheets()
        self.spreadsheet.reorder_worksheets(
            [ws] + [s for s in all_sheets if s.id != ws.id],
        )

    def _setup_schedule_display_row(self, ws: gspread.Worksheet) -> None:
        val = ws.acell("A2").value
        if val == "Date":
            return
        if val:
            ws.insert_row(SCHEDULE_DISPLAY_HEADERS, index=2)
        else:
            ws.update("A2:G2", [SCHEDULE_DISPLAY_HEADERS])

    def _hide_internal_tabs(self) -> None:
        for name in ("RecurringPatterns", "AuditLog", "Configuration"):
            try:
                ws = self.spreadsheet.worksheet(name)
                ws.hide()
            except gspread.WorksheetNotFound:
                pass

    def _protect_sheet_if_needed(
        self, ws: gspread.Worksheet, *, warning_only: bool = True,
    ) -> None:
        metadata = self.spreadsheet.fetch_sheet_metadata()
        for sheet in metadata.get("sheets", []):
            props = sheet.get("properties", {})
            if props.get("sheetId") != ws.id:
                continue
            existing = sheet.get("protectedRanges", [])
            if existing:
                return
        ws.add_protected_range(warning_only=warning_only)

    def _protect_internal_tabs(self) -> None:
        for name in ("RecurringPatterns", "AuditLog", "Configuration"):
            try:
                ws = self.spreadsheet.worksheet(name)
                self._protect_sheet_if_needed(ws, warning_only=True)
            except gspread.WorksheetNotFound:
                pass

    def _apply_schedule_formatting(self, ws: gspread.Worksheet) -> None:
        sheet_id = ws.id
        ws.freeze(rows=2, cols=1)
        ws.format("A2:G2", {
            "textFormat": {"bold": True},
            "backgroundColor": {"red": 0.89, "green": 0.95, "blue": 0.99},
        })
        requests: list = [
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": 0,
                        "endIndex": 1,
                    },
                    "properties": {"pixelSize": 1},
                    "fields": "pixelSize",
                },
            },
            *self._column_width_requests(sheet_id, [(0, 120), (2, 150), (6, 200)]),
            *self._hide_columns_requests(sheet_id, [(3, 6)]),
        ]
        requests.extend(self._conditional_format_requests(sheet_id))
        requests.extend(self._date_validation_requests(sheet_id))
        self.spreadsheet.batch_update({"requests": requests})

    @staticmethod
    def _column_width_requests(
        sheet_id: int, cols: List[tuple],
    ) -> List[dict]:
        return [
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": col,
                        "endIndex": col + 1,
                    },
                    "properties": {"pixelSize": width},
                    "fields": "pixelSize",
                },
            }
            for col, width in cols
        ]

    @staticmethod
    def _hide_columns_requests(
        sheet_id: int, ranges: List[tuple],
    ) -> List[dict]:
        return [
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": start,
                        "endIndex": end,
                    },
                    "properties": {"hiddenByUser": True},
                    "fields": "hiddenByUser",
                },
            }
            for start, end in ranges
        ]

    def _conditional_format_requests(self, sheet_id: int) -> List[dict]:
        clear_requests = self._clear_conditional_format_requests(sheet_id)
        return clear_requests + [
            {
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{
                            "sheetId": sheet_id,
                            "startRowIndex": 2,
                            "startColumnIndex": 0,
                            "endColumnIndex": 7,
                        }],
                        "booleanRule": {
                            "condition": {
                                "type": "CUSTOM_FORMULA",
                                "values": [{"userEnteredValue": '=AND(A3<>"", B3="")'}],
                            },
                            "format": {
                                "backgroundColor": {
                                    "red": 1.0, "green": 0.976, "blue": 0.769,
                                },
                            },
                        },
                    },
                    "index": 0,
                },
            },
            {
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{
                            "sheetId": sheet_id,
                            "startRowIndex": 2,
                            "startColumnIndex": 0,
                            "endColumnIndex": 7,
                        }],
                        "booleanRule": {
                            "condition": {
                                "type": "CUSTOM_FORMULA",
                                "values": [{"userEnteredValue": '=AND(A3<>"", A3<TODAY())'}],
                            },
                            "format": {
                                "backgroundColor": {
                                    "red": 0.96, "green": 0.96, "blue": 0.96,
                                },
                                "textFormat": {
                                    "foregroundColor": {
                                        "red": 0.6, "green": 0.6, "blue": 0.6,
                                    },
                                },
                            },
                        },
                    },
                    "index": 1,
                },
            },
        ]

    def _clear_conditional_format_requests(self, sheet_id: int) -> List[dict]:
        metadata = self.spreadsheet.fetch_sheet_metadata()
        for sheet in metadata.get("sheets", []):
            if sheet.get("properties", {}).get("sheetId") != sheet_id:
                continue
            rules = sheet.get("conditionalFormats", [])
            return [
                {"deleteConditionalFormatRule": {"sheetId": sheet_id, "index": 0}}
                for _ in rules
            ]
        return []

    @staticmethod
    def _date_validation_requests(sheet_id: int) -> List[dict]:
        return [
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 2,
                        "endRowIndex": 1000,
                        "startColumnIndex": 0,
                        "endColumnIndex": 1,
                    },
                    "rule": {
                        "condition": {"type": "DATE_IS_VALID"},
                        "strict": False,
                        "showCustomUi": True,
                    },
                },
            },
        ]

    # -- configuration --
    def load_configuration(self) -> Configuration:
        ws = self._get_or_create("Configuration", CONFIG_HEADERS)
        rows = ws.get_all_records()
        config = Configuration.default()
        for row in rows:
            key = row.get("setting_key", "").strip()
            val = str(row.get("setting_value", "")).strip()
            if not key:
                continue
            try:
                if key in ("warning_passive_days", "warning_urgent_days",
                           "schedule_window_weeks", "cache_ttl_seconds", "max_batch_size"):
                    if val:
                        setattr(config, key, int(val))
                elif key in ("host_role_ids", "admin_role_ids", "owner_user_ids"):
                    parsed = json.loads(val) if val else []
                    setattr(config, key, [int(x) for x in parsed] if parsed else [])
                elif key in ("daily_check_time", "daily_check_timezone", "meeting_pattern"):
                    if val:
                        setattr(config, key, val)
                elif key == "announcement_channel_id":
                    if val:
                        config.announcement_channel_id = val
                elif key in ("warnings_channel_id", "schedule_channel_id"):
                    pass  # handled in legacy fallback below
            except (ValueError, json.JSONDecodeError) as e:
                log.warning("bad config %s=%r: %s", key, val, e)
        # Re-scan rows for legacy channel keys if the new key was not set
        if config.announcement_channel_id is None:
            legacy_order = ("warnings_channel_id", "schedule_channel_id")
            legacy: dict[str, str] = {}
            for row in rows:
                k = row.get("setting_key", "").strip()
                v = str(row.get("setting_value", "")).strip()
                if k in legacy_order and v:
                    legacy[k] = v
            for k in legacy_order:
                if k in legacy:
                    config.announcement_channel_id = legacy[k]
                    break
        return config

    def update_configuration(self, key: str, value: str, type_: str = "json") -> None:
        ws = self._get_or_create("Configuration", CONFIG_HEADERS)
        rows = ws.get_all_values()
        now = datetime.now(timezone.utc).isoformat()
        for idx, row in enumerate(rows[1:], start=2):
            if row and row[0].strip() == key:
                ws.update(f"B{idx}:E{idx}", [[value, type_, row[3] if len(row) > 3 else "", now]])
                return
        ws.append_row([key, value, type_, "", now])

    # -- schedule --
    def load_schedule(self) -> List[EventDate]:
        ws = self._get_or_create("Schedule", SCHEDULE_HEADERS)
        rows = ws.get_all_records()
        out: List[EventDate] = []
        for row in rows:
            raw = str(row.get("date", "")).strip()
            if not raw:
                continue
            try:
                d = parse_iso_date(raw)
            except ValueError:
                continue
            assigned_at = None
            raw_ts = str(row.get("assigned_at", "")).strip()
            if raw_ts:
                try:
                    assigned_at = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                except ValueError:
                    pass
            out.append(EventDate(
                date=d,
                host_discord_id=str(row.get("host_discord_id", "")).strip() or None,
                host_username=str(row.get("host_username", "")).strip() or None,
                recurring_pattern_id=str(row.get("recurring_pattern_id", "")).strip() or None,
                assigned_at=assigned_at,
                assigned_by=str(row.get("assigned_by", "")).strip() or None,
                notes=str(row.get("notes", "")).strip() or None,
            ))
        return out

    def _find_schedule_row(self, ws: gspread.Worksheet, target: str) -> Optional[int]:
        col_values = ws.col_values(1)
        for idx, val in enumerate(col_values[1:], start=2):
            if val.strip() == target:
                return idx
        return None

    def upsert_schedule_row(self, event: EventDate) -> None:
        ws = self._get_or_create("Schedule", SCHEDULE_HEADERS)
        row_values = [
            format_date(event.date),
            _escape_cell(event.host_discord_id or ""),
            _escape_cell(event.host_username or ""),
            _escape_cell(event.recurring_pattern_id or ""),
            event.assigned_at.isoformat() if event.assigned_at else "",
            _escape_cell(event.assigned_by or ""),
            _escape_cell(event.notes or ""),
        ]
        target = format_date(event.date)
        row_idx = self._find_schedule_row(ws, target)
        if row_idx is None:
            ws.append_row(row_values)
        else:
            ws.update(f"A{row_idx}:G{row_idx}", [row_values])

    def clear_schedule_assignment(self, d: date) -> bool:
        ws = self._get_or_create("Schedule", SCHEDULE_HEADERS)
        target = format_date(d)
        row_idx = self._find_schedule_row(ws, target)
        if row_idx is None:
            return False
        ws.update(f"B{row_idx}:G{row_idx}", [["", "", "", "", "", ""]])
        return True

    def delete_future_pattern_rows(self, pattern_id: str, from_date: date) -> int:
        ws = self._get_or_create("Schedule", SCHEDULE_HEADERS)
        rows = ws.get_all_records()
        count = 0
        for idx, row in enumerate(rows, start=2):
            if str(row.get("recurring_pattern_id", "")).strip() != pattern_id:
                continue
            raw = str(row.get("date", "")).strip()
            try:
                d = parse_iso_date(raw)
            except ValueError:
                continue
            if d >= from_date:
                ws.update(f"B{idx}:G{idx}", [["", "", "", "", "", ""]])
                count += 1
        return count

    # -- recurring patterns --
    def load_patterns(self) -> List[RecurringPattern]:
        ws = self._get_or_create("RecurringPatterns", PATTERN_HEADERS)
        rows = ws.get_all_records()
        out: List[RecurringPattern] = []
        for row in rows:
            pid = str(row.get("pattern_id", "")).strip()
            if not pid:
                continue
            try:
                start = parse_iso_date(str(row.get("start_date", "")))
            except ValueError:
                continue
            end_raw = str(row.get("end_date", "")).strip()
            end = None
            if end_raw:
                try:
                    end = parse_iso_date(end_raw)
                except ValueError:
                    pass
            is_active = str(row.get("is_active", "TRUE")).strip().upper() != "FALSE"
            out.append(RecurringPattern(
                pattern_id=pid,
                host_discord_id=str(row.get("host_discord_id", "")),
                host_username=str(row.get("host_username", "")),
                pattern_description=str(row.get("pattern_description", "")),
                pattern_rule=str(row.get("pattern_rule", "")),
                start_date=start,
                end_date=end,
                is_active=is_active,
            ))
        return out

    def append_pattern(self, pattern: RecurringPattern) -> None:
        ws = self._get_or_create("RecurringPatterns", PATTERN_HEADERS)
        ws.append_row([
            _escape_cell(pattern.pattern_id),
            _escape_cell(pattern.host_discord_id),
            _escape_cell(pattern.host_username),
            _escape_cell(pattern.pattern_description),
            _escape_cell(pattern.pattern_rule),
            format_date(pattern.start_date),
            format_date(pattern.end_date) if pattern.end_date else "",
            (pattern.created_at or datetime.now(timezone.utc)).isoformat(),
            "TRUE" if pattern.is_active else "FALSE",
        ])

    def deactivate_pattern(self, pattern_id: str) -> bool:
        ws = self._get_or_create("RecurringPatterns", PATTERN_HEADERS)
        col = ws.col_values(1)
        for idx, val in enumerate(col[1:], start=2):
            if val.strip() == pattern_id:
                ws.update(f"I{idx}", [["FALSE"]])
                return True
        return False

    # -- audit --
    def append_audit(self, entry: AuditEntry) -> None:
        ws = self._get_or_create("AuditLog", AUDIT_HEADERS)
        ws.append_row([
            _escape_cell(entry.entry_id),
            entry.timestamp.isoformat(),
            _escape_cell(entry.action_type),
            _escape_cell(entry.user_discord_id),
            _escape_cell(entry.target_user_discord_id or ""),
            format_date(entry.event_date) if entry.event_date else "",
            _escape_cell(entry.recurring_pattern_id or ""),
            _escape_cell(entry.outcome),
            _escape_cell(entry.error_message or ""),
            json.dumps(entry.metadata) if entry.metadata else "",
        ])


def make_audit(
    action_type: str,
    user_discord_id: str,
    *,
    target_user_discord_id: Optional[str] = None,
    event_date: Optional[date] = None,
    recurring_pattern_id: Optional[str] = None,
    outcome: str = "success",
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AuditEntry:
    return AuditEntry(
        entry_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        action_type=action_type,
        user_discord_id=user_discord_id,
        target_user_discord_id=target_user_discord_id,
        event_date=event_date,
        recurring_pattern_id=recurring_pattern_id,
        outcome=outcome,
        error_message=error_message,
        metadata=metadata or {},
    )
