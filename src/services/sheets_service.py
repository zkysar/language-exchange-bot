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

SCHEDULE_HEADERS = [
    "date", "host_discord_id", "host_username", "recurring_pattern_id",
    "assigned_at", "assigned_by", "notes",
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
    ("warning_passive_days", "7", "integer", "Days before event to post passive warning"),
    ("warning_urgent_days", "3", "integer", "Days before event to post urgent warning"),
    ("daily_check_time", "09:00", "string", "Time of day for daily warning check (HH:MM)"),
    ("daily_check_timezone", "America/Los_Angeles", "string", "IANA timezone"),
    ("schedule_window_weeks", "4", "integer", "Default weeks shown in /schedule"),
    ("member_role_ids", "[]", "json", "Discord role IDs for members"),
    ("host_role_ids", "[]", "json", "Discord role IDs for hosts"),
    ("admin_role_ids", "[]", "json", "Discord role IDs for admins"),
    ("schedule_channel_id", "", "string", "Discord channel ID for schedule posts"),
    ("warnings_channel_id", "", "string", "Discord channel ID for warning posts"),
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
                elif key in ("member_role_ids", "host_role_ids", "admin_role_ids"):
                    parsed = json.loads(val) if val else []
                    setattr(config, key, [int(x) for x in parsed] if parsed else [])
                elif key in ("daily_check_time", "daily_check_timezone"):
                    if val:
                        setattr(config, key, val)
                elif key in ("schedule_channel_id", "warnings_channel_id"):
                    setattr(config, key, val or None)
            except (ValueError, json.JSONDecodeError) as e:
                log.warning("bad config %s=%r: %s", key, val, e)
        return config

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
            event.host_discord_id or "",
            event.host_username or "",
            event.recurring_pattern_id or "",
            event.assigned_at.isoformat() if event.assigned_at else "",
            event.assigned_by or "",
            event.notes or "",
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
            pattern.pattern_id,
            pattern.host_discord_id,
            pattern.host_username,
            pattern.pattern_description,
            pattern.pattern_rule,
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
            entry.entry_id,
            entry.timestamp.isoformat(),
            entry.action_type,
            entry.user_discord_id,
            entry.target_user_discord_id or "",
            format_date(entry.event_date) if entry.event_date else "",
            entry.recurring_pattern_id or "",
            entry.outcome,
            entry.error_message or "",
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
