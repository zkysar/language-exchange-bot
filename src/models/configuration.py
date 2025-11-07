"""Configuration entity model."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class SettingType(str, Enum):
    """Types of configuration settings."""

    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    JSON = "json"


@dataclass
class Configuration:
    """
    Represents a system setting stored in Google Sheets.

    Attributes:
        setting_key: Configuration parameter name (unique)
        setting_value: Configuration value (may be JSON for complex types)
        setting_type: Type of value (string, integer, boolean, datetime, json)
        description: Human-readable description of setting
        updated_at: Last modification timestamp
    """

    setting_key: str
    setting_value: str
    setting_type: SettingType
    description: Optional[str] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        """Validate configuration data."""
        if not isinstance(self.setting_key, str) or not self.setting_key:
            raise ValueError("setting_key must be a non-empty string")

        if not isinstance(self.setting_type, SettingType):
            if isinstance(self.setting_type, str):
                self.setting_type = SettingType(self.setting_type)
            else:
                raise ValueError("setting_type must be SettingType enum or string")

    def get_typed_value(self) -> Any:
        """
        Parse setting_value according to setting_type.

        Returns:
            Typed value based on setting_type

        Raises:
            ValueError: If value cannot be parsed according to type
        """
        import json

        if self.setting_type == SettingType.STRING:
            return self.setting_value
        elif self.setting_type == SettingType.INTEGER:
            return int(self.setting_value)
        elif self.setting_type == SettingType.BOOLEAN:
            return self.setting_value.lower() in ("true", "1", "yes")
        elif self.setting_type == SettingType.DATETIME:
            return datetime.fromisoformat(self.setting_value)
        elif self.setting_type == SettingType.JSON:
            return json.loads(self.setting_value)
        else:
            raise ValueError(f"Unknown setting type: {self.setting_type}")

    @classmethod
    def from_dict(cls, data: dict) -> "Configuration":
        """Create Configuration instance from dictionary."""
        return cls(
            setting_key=data["setting_key"],
            setting_value=data["setting_value"],
            setting_type=SettingType(data["setting_type"]),
            description=data.get("description"),
            updated_at=datetime.fromisoformat(data["updated_at"])
            if data.get("updated_at")
            else None,
        )

    def to_dict(self) -> dict:
        """Convert Configuration to dictionary for serialization."""
        return {
            "setting_key": self.setting_key,
            "setting_value": self.setting_value,
            "setting_type": self.setting_type.value,
            "description": self.description,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# Default configuration values
DEFAULT_CONFIG = {
    "warning_passive_days": ("7", SettingType.INTEGER, "Days before event to post passive warning"),
    "warning_urgent_days": ("3", SettingType.INTEGER, "Days before event to post urgent warning"),
    "daily_check_time": ("09:00", SettingType.STRING, "Time of day for daily warning check (PST)"),
    "schedule_window_weeks": ("8", SettingType.INTEGER, "Default weeks to show in schedule view"),
    "organizer_role_ids": ("[]", SettingType.JSON, "Discord role IDs that can use admin commands"),
    "host_privileged_role_ids": (
        "[]",
        SettingType.JSON,
        "Discord role IDs that can volunteer for others",
    ),
    "schedule_channel_id": ("", SettingType.STRING, "Discord channel ID for schedule displays"),
    "warnings_channel_id": ("", SettingType.STRING, "Discord channel ID for warning posts"),
    "cache_ttl_seconds": (
        "300",
        SettingType.INTEGER,
        "Cache TTL for Google Sheets data (5 minutes)",
    ),
    "max_batch_size": (
        "100",
        SettingType.INTEGER,
        "Maximum rows to batch in Google Sheets API calls",
    ),
}


def get_default_configurations() -> list[Configuration]:
    """
    Get list of default Configuration objects.

    Returns:
        List of Configuration objects with default values
    """
    configs = []
    for key, (value, setting_type, description) in DEFAULT_CONFIG.items():
        configs.append(
            Configuration(
                setting_key=key,
                setting_value=value,
                setting_type=setting_type,
                description=description,
                updated_at=datetime.now(),
            )
        )
    return configs
