from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple
from zoneinfo import available_timezones

from src.utils.pattern_parser import parse_pattern


@dataclass(frozen=True)
class SettingMeta:
    group: str
    label: str
    setting_type: str
    config_key: str
    sheets_type: str
    description: str
    min_val: Optional[int] = None
    max_val: Optional[int] = None
    nullable: bool = False


SETTINGS: dict[str, SettingMeta] = {
    "schedule_announcement_interval_days": SettingMeta(
        group="announcements",
        label="Schedule post interval (days)",
        setting_type="integer",
        config_key="schedule_announcement_interval_days",
        sheets_type="integer",
        description="Days between schedule announcement posts (empty = off)",
        min_val=1,
        max_val=365,
        nullable=True,
    ),
    "schedule_announcement_lookahead_weeks": SettingMeta(
        group="announcements",
        label="Schedule post lookahead (weeks)",
        setting_type="integer",
        config_key="schedule_announcement_lookahead_weeks",
        sheets_type="integer",
        description="Weeks ahead to list in each schedule announcement (empty = off)",
        min_val=1,
        max_val=26,
        nullable=True,
    ),
    "warning_passive_days": SettingMeta(
        group="announcements",
        label="Passive warning days",
        setting_type="integer",
        config_key="warning_passive_days",
        sheets_type="integer",
        description="Days before an unassigned date to post a passive warning (empty = off)",
        min_val=1,
        max_val=30,
        nullable=True,
    ),
    "warning_urgent_days": SettingMeta(
        group="announcements",
        label="Urgent warning days",
        setting_type="integer",
        config_key="warning_urgent_days",
        sheets_type="integer",
        description="Days before an unassigned date to post an urgent warning (empty = off)",
        min_val=1,
        max_val=14,
        nullable=True,
    ),
    "announcement_channel_id": SettingMeta(
        group="announcements",
        label="Announcement channel",
        setting_type="channel",
        config_key="announcement_channel_id",
        sheets_type="string",
        description="Channel where the bot posts schedule announcements and host-needed warnings",
    ),
    "schedule_window_weeks": SettingMeta(
        group="schedule",
        label="Schedule window (weeks)",
        setting_type="integer",
        config_key="schedule_window_weeks",
        sheets_type="integer",
        description="Default number of weeks shown in /schedule",
        min_val=1,
        max_val=12,
    ),
    "daily_check_time": SettingMeta(
        group="schedule",
        label="Daily check time",
        setting_type="time",
        config_key="daily_check_time",
        sheets_type="string",
        description="Time of day for the automated warning check (HH:MM, 24-hour)",
    ),
    "daily_check_timezone": SettingMeta(
        group="schedule",
        label="Timezone",
        setting_type="timezone",
        config_key="daily_check_timezone",
        sheets_type="string",
        description="IANA timezone for the daily check (e.g. America/Los_Angeles)",
    ),
    "meeting_schedule": SettingMeta(
        group="schedule",
        label="Meeting schedule",
        setting_type="pattern",
        config_key="meeting_schedule",
        sheets_type="string",
        description="When the exchange meets (e.g. 'every wednesday', 'every 2nd tuesday'). Leave blank to allow any date.",
    ),
}

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_VALID_TIMEZONES = available_timezones()


def validate_setting(key: str, value: str) -> Tuple[bool, Optional[str], Optional[str]]:
    meta = SETTINGS.get(key)
    if meta is None:
        return False, None, f"Unknown setting: `{key}`"

    if meta.nullable and value == "":
        return True, "", None

    if meta.setting_type == "integer":
        try:
            n = int(value)
        except ValueError:
            return False, None, f"`{meta.label}` must be an integer."
        if meta.min_val is not None and n < meta.min_val:
            return False, None, f"`{meta.label}` must be between {meta.min_val} and {meta.max_val}."
        if meta.max_val is not None and n > meta.max_val:
            return False, None, f"`{meta.label}` must be between {meta.min_val} and {meta.max_val}."
        return True, str(n), None

    if meta.setting_type == "time":
        if not _TIME_RE.match(value):
            return False, None, f"`{meta.label}` must be in HH:MM 24-hour format (e.g. 09:00)."
        return True, value, None

    if meta.setting_type == "timezone":
        if value not in _VALID_TIMEZONES:
            return False, None, f"`{value}` is not a valid IANA timezone."
        return True, value, None

    if meta.setting_type == "channel":
        return True, value, None

    if meta.setting_type == "pattern":
        if value == "":
            return True, "", None
        try:
            parse_pattern(value)
        except ValueError as e:
            return False, None, f"`{meta.label}`: {e}"
        return True, value, None

    return False, None, f"Unknown type for `{key}`."
