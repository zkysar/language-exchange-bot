from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional


@dataclass
class Host:
    discord_id: str
    discord_username: str = ""
    created_at: Optional[datetime] = None


@dataclass
class EventDate:
    date: date
    host_discord_id: Optional[str] = None
    host_username: Optional[str] = None
    recurring_pattern_id: Optional[str] = None
    assigned_at: Optional[datetime] = None
    assigned_by: Optional[str] = None
    notes: Optional[str] = None

    @property
    def is_assigned(self) -> bool:
        return bool(self.host_discord_id)


@dataclass
class RecurringPattern:
    pattern_id: str
    host_discord_id: str
    host_username: str
    pattern_description: str
    pattern_rule: str
    start_date: date
    end_date: Optional[date] = None
    created_at: Optional[datetime] = None
    is_active: bool = True


@dataclass
class AuditEntry:
    entry_id: str
    timestamp: datetime
    action_type: str
    user_discord_id: str
    target_user_discord_id: Optional[str] = None
    event_date: Optional[date] = None
    recurring_pattern_id: Optional[str] = None
    outcome: str = "success"
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Configuration:
    warning_passive_days: int = 4
    warning_urgent_days: int = 1
    daily_check_time: str = "09:00"
    daily_check_timezone: str = "America/Los_Angeles"
    schedule_window_weeks: int = 2
    host_role_ids: List[int] = field(default_factory=list)
    admin_role_ids: List[int] = field(default_factory=list)
    owner_user_ids: List[int] = field(default_factory=list)
    announcement_channel_id: Optional[str] = None
    meeting_pattern: Optional[str] = None
    cache_ttl_seconds: int = 300
    max_batch_size: int = 100

    @classmethod
    def default(cls) -> "Configuration":
        return cls()
