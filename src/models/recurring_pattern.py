"""RecurringPattern entity model."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class RecurringPattern:
    """
    Represents a schedule rule defining regular hosting commitments.

    Attributes:
        pattern_id: Unique identifier (UUID or generated ID)
        host_discord_id: Discord ID of host who owns this pattern
        pattern_description: Human-readable pattern (e.g., "every 2nd Tuesday")
        pattern_rule: Machine-readable pattern rule (JSON string for dateutil.relativedelta)
        start_date: First date this pattern applies
        end_date: Last date this pattern applies, None for indefinite
        created_at: Timestamp when pattern was created
        is_active: Whether pattern is currently active (False when cancelled)
    """

    pattern_id: str
    host_discord_id: str
    pattern_description: str
    pattern_rule: str
    start_date: date
    end_date: Optional[date] = None
    created_at: Optional[datetime] = None
    is_active: bool = True

    def __post_init__(self):
        """Validate pattern data."""
        if not isinstance(self.pattern_id, str) or not self.pattern_id:
            raise ValueError("pattern_id must be a non-empty string")

        if not isinstance(self.host_discord_id, str):
            raise ValueError("host_discord_id must be a string")
        if not self.host_discord_id.isdigit():
            raise ValueError("host_discord_id must be numeric")
        if len(self.host_discord_id) < 17 or len(self.host_discord_id) > 19:
            raise ValueError("host_discord_id must be 17-19 digits")

        if not isinstance(self.start_date, date):
            raise ValueError("start_date must be a datetime.date object")

        if self.end_date is not None:
            if not isinstance(self.end_date, date):
                raise ValueError("end_date must be a datetime.date object")
            if self.end_date <= self.start_date:
                raise ValueError("end_date must be after start_date")

    @classmethod
    def from_dict(cls, data: dict) -> "RecurringPattern":
        """Create RecurringPattern instance from dictionary."""
        return cls(
            pattern_id=data["pattern_id"],
            host_discord_id=data["host_discord_id"],
            pattern_description=data["pattern_description"],
            pattern_rule=data["pattern_rule"],
            start_date=date.fromisoformat(data["start_date"]),
            end_date=date.fromisoformat(data["end_date"]) if data.get("end_date") else None,
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else None,
            is_active=data.get("is_active", True),
        )

    def to_dict(self) -> dict:
        """Convert RecurringPattern to dictionary for serialization."""
        return {
            "pattern_id": self.pattern_id,
            "host_discord_id": self.host_discord_id,
            "pattern_description": self.pattern_description,
            "pattern_rule": self.pattern_rule,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_active": self.is_active,
        }
