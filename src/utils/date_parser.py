"""Date parsing and validation utilities."""

from datetime import date, datetime
from typing import Optional

import pytz

# PST timezone
PST = pytz.timezone("America/Los_Angeles")


def parse_date(date_str: str) -> Optional[date]:
    """
    Parse date string in YYYY-MM-DD format.

    Args:
        date_str: Date string to parse

    Returns:
        Parsed date object if valid, None otherwise

    Raises:
        ValueError: If date format is invalid
    """
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
        return parsed
    except ValueError as e:
        raise ValueError(
            f"Invalid date format: '{date_str}'. Expected YYYY-MM-DD (e.g., 2025-11-11)"
        ) from e


def validate_future_date(target_date: date) -> None:
    """
    Validate that date is in the future (PST timezone).

    Args:
        target_date: Date to validate

    Raises:
        ValueError: If date is not in the future
    """
    # Get current date in PST
    now_pst = datetime.now(PST).date()

    if target_date <= now_pst:
        raise ValueError(
            f"Date must be in the future. "
            f"Today is {now_pst.isoformat()} (PST), you provided {target_date.isoformat()}"
        )


def validate_date_format_and_future(date_str: str) -> date:
    """
    Parse and validate that date is in YYYY-MM-DD format and in the future.

    Args:
        date_str: Date string to parse and validate

    Returns:
        Parsed and validated date object

    Raises:
        ValueError: If date format is invalid or date is not in the future
    """
    parsed_date = parse_date(date_str)
    validate_future_date(parsed_date)
    return parsed_date


def format_date_pst(target_date: date) -> str:
    """
    Format date as human-readable string with PST timezone.

    Args:
        target_date: Date to format

    Returns:
        Formatted date string (e.g., "Tuesday, November 11, 2025 (PST)")
    """
    # Create datetime in PST for proper formatting
    dt = datetime.combine(target_date, datetime.min.time())
    dt_pst = PST.localize(dt)

    # Format: "Tuesday, November 11, 2025 (PST)"
    return dt_pst.strftime("%A, %B %d, %Y") + " (PST)"


def get_current_date_pst() -> date:
    """
    Get current date in PST timezone.

    Returns:
        Current date in PST
    """
    return datetime.now(PST).date()
