"""Commands package for Discord Host Scheduler Bot."""

from .schedule import register_schedule_command
from .sync import register_sync_command
from .unvolunteer import register_unvolunteer_command
from .volunteer import register_volunteer_command
from .warnings import register_warnings_command

__all__ = [
    "register_volunteer_command",
    "register_unvolunteer_command",
    "register_schedule_command",
    "register_sync_command",
    "register_warnings_command",
]
