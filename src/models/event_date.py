"""EventDate entity model."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class EventDate:
    """
    Represents a specific calendar date that needs a host, with optional host assignment.

    Attributes:
        date: Calendar date in YYYY-MM-DD format
        host_discord_id: Discord ID of assigned host, None if unassigned
        recurring_pattern_id: Reference to recurring pattern if assigned via pattern
        assigned_at: Timestamp when host was assigned
        assigned_by: Discord ID of user who made the assignment (for proxy actions)
        notes: Optional notes about the event
    """

    date: date
    host_discord_id: Optional[str] = None
    recurring_pattern_id: Optional[str] = None
    assigned_at: Optional[datetime] = None
    assigned_by: Optional[str] = None
    notes: Optional[str] = None

    def __post_init__(self):
        """Validate date and host_discord_id formats."""
        if not isinstance(self.date, date):
            raise ValueError("date must be a datetime.date object")

        if self.host_discord_id is not None:
            if not isinstance(self.host_discord_id, str):
                raise ValueError("host_discord_id must be a string")
            if not self.host_discord_id.isdigit():
                raise ValueError("host_discord_id must be numeric")
            if len(self.host_discord_id) < 17 or len(self.host_discord_id) > 19:
                raise ValueError("host_discord_id must be 17-19 digits")

    def is_assigned(self) -> bool:
        """Check if this date has an assigned host."""
        return self.host_discord_id is not None

    @classmethod
    def from_dict(cls, data: dict) -> "EventDate":
        """Create EventDate instance from dictionary."""
        event_date = date.fromisoformat(data["date"])
        return cls(
            date=event_date,
            host_discord_id=data.get("host_discord_id"),
            recurring_pattern_id=data.get("recurring_pattern_id"),
            assigned_at=datetime.fromisoformat(data["assigned_at"])
            if data.get("assigned_at")
            else None,
            assigned_by=data.get("assigned_by"),
            notes=data.get("notes"),
        )

    def to_dict(self) -> dict:
        """Convert EventDate to dictionary for serialization."""
        return {
            "date": self.date.isoformat(),
            "host_discord_id": self.host_discord_id,
            "recurring_pattern_id": self.recurring_pattern_id,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "assigned_by": self.assigned_by,
            "notes": self.notes,
        }
