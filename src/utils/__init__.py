"""Utilities package for Discord Host Scheduler Bot."""

from .auth import (
    authorize_admin_command,
    authorize_proxy_action,
    check_host_privileged_role,
    check_organizer_role,
    has_role_by_id,
)
from .date_parser import (
    format_date_pst,
    get_current_date_pst,
    parse_date,
    validate_date_format_and_future,
    validate_future_date,
)
from .logger import log_with_context, sanitize_log_data, setup_logging
from .pattern_parser import (
    format_pattern_preview,
    generate_dates_from_pattern,
    parse_pattern_description,
    pattern_rule_from_json,
    pattern_rule_to_json,
)

__all__ = [
    # Auth
    "has_role_by_id",
    "check_organizer_role",
    "check_host_privileged_role",
    "authorize_proxy_action",
    "authorize_admin_command",
    # Date parser
    "parse_date",
    "validate_future_date",
    "validate_date_format_and_future",
    "format_date_pst",
    "get_current_date_pst",
    # Logger
    "setup_logging",
    "log_with_context",
    "sanitize_log_data",
    # Pattern parser
    "parse_pattern_description",
    "pattern_rule_to_json",
    "pattern_rule_from_json",
    "generate_dates_from_pattern",
    "format_pattern_preview",
]
