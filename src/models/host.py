"""Host entity model."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Host:
    """
    Represents a Discord user who can volunteer to host events.

    Attributes:
        discord_id: Discord user ID (snowflake format, 17-19 digits)
        discord_username: Discord username for display (e.g., "user#1234")
        created_at: Timestamp when first recorded
    """

    discord_id: str
    discord_username: Optional[str] = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        """Validate discord_id format."""
        if not isinstance(self.discord_id, str):
            raise ValueError("discord_id must be a string")

        if not self.discord_id.isdigit():
            raise ValueError("discord_id must be numeric")

        if len(self.discord_id) < 17 or len(self.discord_id) > 19:
            raise ValueError("discord_id must be 17-19 digits (Discord snowflake format)")

    @classmethod
    def from_dict(cls, data: dict) -> "Host":
        """Create Host instance from dictionary."""
        return cls(
            discord_id=data["discord_id"],
            discord_username=data.get("discord_username"),
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else None,
        )

    def to_dict(self) -> dict:
        """Convert Host to dictionary for serialization."""
        return {
            "discord_id": self.discord_id,
            "discord_username": self.discord_username,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
