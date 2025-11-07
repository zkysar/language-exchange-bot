"""Commands package for Discord Host Scheduler Bot."""

from .schedule import register_schedule_command
from .sync import register_sync_command
from .volunteer import register_volunteer_command

__all__ = [
    "register_volunteer_command",
    "register_schedule_command",
    "register_sync_command",
]
