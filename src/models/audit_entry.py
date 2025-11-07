"""AuditEntry entity model."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Optional


class ActionType(str, Enum):
    """Types of actions that can be audited."""

    VOLUNTEER = "VOLUNTEER"
    UNVOLUNTEER = "UNVOLUNTEER"
    VOLUNTEER_RECURRING = "VOLUNTEER_RECURRING"
    UNVOLUNTEER_RECURRING = "UNVOLUNTEER_RECURRING"
    VIEW_SCHEDULE = "VIEW_SCHEDULE"
    WARNING_POSTED = "WARNING_POSTED"
    SYNC_FORCED = "SYNC_FORCED"
    RESET = "RESET"


class Outcome(str, Enum):
    """Outcome of an action."""

    SUCCESS = "success"
    FAILURE = "failure"


@dataclass
class AuditEntry:
    """
    Represents a log record of system actions for accountability and debugging.

    Attributes:
        entry_id: Unique identifier (UUID or generated ID)
        timestamp: When action occurred
        action_type: Type of action (see ActionType enum)
        user_discord_id: Discord ID of user who initiated action
        target_user_discord_id: Discord ID of affected user (for proxy actions)
        event_date: Date affected by action (if applicable)
        recurring_pattern_id: Pattern affected by action (if applicable)
        outcome: "success" or "failure"
        error_message: Error message if outcome is "failure"
        metadata: Additional context (command parameters, API response codes)
    """

    entry_id: str
    timestamp: datetime
    action_type: ActionType
    user_discord_id: str
    outcome: Outcome
    target_user_discord_id: Optional[str] = None
    event_date: Optional[date] = None
    recurring_pattern_id: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

    def __post_init__(self):
        """Validate audit entry data."""
        if not isinstance(self.entry_id, str) or not self.entry_id:
            raise ValueError("entry_id must be a non-empty string")

        if not isinstance(self.timestamp, datetime):
            raise ValueError("timestamp must be a datetime object")

        if not isinstance(self.action_type, ActionType):
            if isinstance(self.action_type, str):
                self.action_type = ActionType(self.action_type)
            else:
                raise ValueError("action_type must be ActionType enum or string")

        if not isinstance(self.outcome, Outcome):
            if isinstance(self.outcome, str):
                self.outcome = Outcome(self.outcome)
            else:
                raise ValueError("outcome must be Outcome enum or string")

        if self.outcome == Outcome.FAILURE and not self.error_message:
            raise ValueError("error_message must be provided when outcome is failure")

    @classmethod
    def from_dict(cls, data: dict) -> "AuditEntry":
        """Create AuditEntry instance from dictionary."""
        return cls(
            entry_id=data["entry_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            action_type=ActionType(data["action_type"]),
            user_discord_id=data["user_discord_id"],
            outcome=Outcome(data["outcome"]),
            target_user_discord_id=data.get("target_user_discord_id"),
            event_date=date.fromisoformat(data["event_date"]) if data.get("event_date") else None,
            recurring_pattern_id=data.get("recurring_pattern_id"),
            error_message=data.get("error_message"),
            metadata=data.get("metadata"),
        )

    def to_dict(self) -> dict:
        """Convert AuditEntry to dictionary for serialization."""
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp.isoformat(),
            "action_type": self.action_type.value,
            "user_discord_id": self.user_discord_id,
            "target_user_discord_id": self.target_user_discord_id,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "recurring_pattern_id": self.recurring_pattern_id,
            "outcome": self.outcome.value,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }
