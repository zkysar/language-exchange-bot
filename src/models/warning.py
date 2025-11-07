"""Warning entity model."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Optional


class WarningSeverity(str, Enum):
    """Warning severity levels."""

    PASSIVE = "passive"
    URGENT = "urgent"


@dataclass
class Warning:
    """
    Represents an alert about an unassigned date that needs attention.

    Attributes:
        warning_id: Unique identifier (UUID or generated ID)
        event_date: Date that needs a host
        severity: "passive" (7+ days away) or "urgent" (3 days away)
        days_until_event: Number of days until event date
        posted_at: Timestamp when warning was posted to Discord
        posted_channel_id: Discord channel ID where warning was posted
        resolved_at: Timestamp when warning was resolved (date assigned)
    """

    warning_id: str
    event_date: date
    severity: WarningSeverity
    days_until_event: int
    posted_at: Optional[datetime] = None
    posted_channel_id: Optional[str] = None
    resolved_at: Optional[datetime] = None

    def __post_init__(self):
        """Validate warning data."""
        if not isinstance(self.warning_id, str) or not self.warning_id:
            raise ValueError("warning_id must be a non-empty string")

        if not isinstance(self.event_date, date):
            raise ValueError("event_date must be a datetime.date object")

        if not isinstance(self.severity, WarningSeverity):
            if isinstance(self.severity, str):
                self.severity = WarningSeverity(self.severity)
            else:
                raise ValueError("severity must be WarningSeverity enum or string")

        if not isinstance(self.days_until_event, int) or self.days_until_event < 0:
            raise ValueError("days_until_event must be a non-negative integer")

    def is_posted(self) -> bool:
        """Check if warning has been posted to Discord."""
        return self.posted_at is not None

    def is_resolved(self) -> bool:
        """Check if warning has been resolved."""
        return self.resolved_at is not None

    @classmethod
    def from_dict(cls, data: dict) -> "Warning":
        """Create Warning instance from dictionary."""
        return cls(
            warning_id=data["warning_id"],
            event_date=date.fromisoformat(data["event_date"]),
            severity=WarningSeverity(data["severity"]),
            days_until_event=data["days_until_event"],
            posted_at=datetime.fromisoformat(data["posted_at"]) if data.get("posted_at") else None,
            posted_channel_id=data.get("posted_channel_id"),
            resolved_at=datetime.fromisoformat(data["resolved_at"])
            if data.get("resolved_at")
            else None,
        )

    def to_dict(self) -> dict:
        """Convert Warning to dictionary for serialization."""
        return {
            "warning_id": self.warning_id,
            "event_date": self.event_date.isoformat(),
            "severity": self.severity.value,
            "days_until_event": self.days_until_event,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
            "posted_channel_id": self.posted_channel_id,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
