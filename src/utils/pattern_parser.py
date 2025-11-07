"""Recurring pattern parsing utilities."""

import json
import re
from datetime import date, timedelta
from typing import Optional

from dateutil.relativedelta import FR, MO, SA, SU, TH, TU, WE, relativedelta

# Weekday mapping
WEEKDAY_MAP = {
    "monday": MO,
    "tuesday": TU,
    "wednesday": WE,
    "thursday": TH,
    "friday": FR,
    "saturday": SA,
    "sunday": SU,
    "mon": MO,
    "tue": TU,
    "wed": WE,
    "thu": TH,
    "fri": FR,
    "sat": SA,
    "sun": SU,
}


def parse_pattern_description(description: str) -> Optional[dict]:
    """
    Parse human-readable pattern description into machine-readable rule.

    Supported formats:
    - "every Nth [weekday]" (e.g., "every 2nd Tuesday", "every 1st Friday")
    - "monthly" (1st of every month)
    - "biweekly" (every 2 weeks)
    - "weekly" (every week)

    Args:
        description: Human-readable pattern description

    Returns:
        Dictionary representing relativedelta parameters, or None if invalid

    Raises:
        ValueError: If pattern cannot be parsed
    """
    description = description.lower().strip()

    # Pattern: "every Nth weekday" (e.g., "every 2nd tuesday")
    match = re.match(r"every\s+(\d+)(?:st|nd|rd|th)\s+(\w+)", description)
    if match:
        nth = int(match.group(1))
        weekday_name = match.group(2)

        if weekday_name not in WEEKDAY_MAP:
            raise ValueError(
                f"Invalid weekday: '{weekday_name}'. "
                f"Valid options: {', '.join(set(WEEKDAY_MAP.keys()))}"
            )

        weekday = WEEKDAY_MAP[weekday_name]
        # Store as dict for JSON serialization
        return {"type": "nth_weekday", "nth": nth, "weekday": weekday.weekday}

    # Pattern: "monthly"
    if description == "monthly":
        return {"type": "monthly"}

    # Pattern: "biweekly"
    if description in ("biweekly", "bi-weekly"):
        return {"type": "biweekly"}

    # Pattern: "weekly"
    if description == "weekly":
        return {"type": "weekly"}

    raise ValueError(
        f"Cannot parse pattern: '{description}'. "
        f"Supported formats: 'every Nth weekday', 'monthly', 'biweekly', 'weekly'"
    )


def pattern_rule_to_json(pattern_dict: dict) -> str:
    """
    Convert pattern dictionary to JSON string for storage.

    Args:
        pattern_dict: Pattern dictionary from parse_pattern_description

    Returns:
        JSON string representation of pattern
    """
    return json.dumps(pattern_dict)


def pattern_rule_from_json(pattern_json: str) -> dict:
    """
    Parse pattern JSON string back to dictionary.

    Args:
        pattern_json: JSON string representation of pattern

    Returns:
        Pattern dictionary
    """
    return json.loads(pattern_json)


def generate_dates_from_pattern(
    pattern_dict: dict, start_date: date, end_date: Optional[date], months: int = 3
) -> list[date]:
    """
    Generate list of dates matching the pattern.

    Args:
        pattern_dict: Pattern dictionary from parse_pattern_description
        start_date: First date to consider
        end_date: Last date to consider (None for indefinite)
        months: Number of months to generate (default 3)

    Returns:
        List of dates matching the pattern

    Raises:
        ValueError: If pattern type is unknown
    """
    pattern_type = pattern_dict.get("type")
    dates = []

    # Calculate limit date (end_date or start_date + months)
    if end_date:
        limit_date = end_date
    else:
        limit_date = start_date + relativedelta(months=months)

    current_date = start_date

    if pattern_type == "nth_weekday":
        # Every Nth weekday of the month
        nth = pattern_dict["nth"]
        weekday = pattern_dict["weekday"]

        # Map weekday number to relativedelta weekday class
        weekday_map = {
            0: MO,
            1: TU,
            2: WE,
            3: TH,
            4: FR,
            5: SA,
            6: SU,
        }

        if weekday not in weekday_map:
            raise ValueError(f"Invalid weekday number: {weekday}")

        weekday_class = weekday_map[weekday]

        while current_date <= limit_date:
            # Get the Nth weekday of current month
            # Start from first day of month
            first_of_month = current_date.replace(day=1)
            # Find the Nth occurrence of weekday using relativedelta
            # relativedelta(weekday=MO(+1)) means first Monday, MO(+2) means second Monday, etc.
            target_date = first_of_month + relativedelta(weekday=weekday_class(+nth))

            # Only add if it's within our date range
            if start_date <= target_date <= limit_date:
                dates.append(target_date)

            # Move to next month
            current_date = current_date + relativedelta(months=1)
            current_date = current_date.replace(day=1)

    elif pattern_type == "monthly":
        # 1st of every month
        while current_date <= limit_date:
            target_date = current_date.replace(day=1)
            if start_date <= target_date <= limit_date:
                dates.append(target_date)
            current_date = current_date + relativedelta(months=1)

    elif pattern_type == "biweekly":
        # Every 2 weeks from start_date
        current_date = start_date
        while current_date <= limit_date:
            dates.append(current_date)
            current_date = current_date + timedelta(weeks=2)

    elif pattern_type == "weekly":
        # Every week from start_date
        current_date = start_date
        while current_date <= limit_date:
            dates.append(current_date)
            current_date = current_date + timedelta(weeks=1)

    else:
        raise ValueError(f"Unknown pattern type: {pattern_type}")

    return dates


def format_pattern_preview(dates: list[date]) -> str:
    """
    Format list of dates as human-readable preview.

    Args:
        dates: List of dates to format

    Returns:
        Formatted string showing dates
    """
    if not dates:
        return "No dates generated"

    # Show first 5 dates
    preview_dates = dates[:5]
    formatted = [d.strftime("%A, %B %d, %Y") for d in preview_dates]

    result = ", ".join(formatted)

    if len(dates) > 5:
        result += f", ... ({len(dates) - 5} more dates)"

    return result
