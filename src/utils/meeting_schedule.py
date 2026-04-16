"""Shared predicate module for the `meeting_schedule` config setting.

When `Configuration.meeting_schedule` is unset, every day is a valid meeting
day (current behavior preserved). When set, the string is parsed with
`parse_pattern` and only dates matching that recurrence count.

Consumers: `hosting.py`, `schedule.py`, `warning_service.py`.
"""
from __future__ import annotations

from datetime import date
from typing import Optional, Set, Tuple

from src.models.models import Configuration
from src.utils.pattern_parser import generate_dates, parse_pattern


def is_meeting_day(d: date, config: Configuration) -> bool:
    """Return True if `d` is a valid meeting day under `config.meeting_schedule`.

    Returns True when the schedule is unset OR malformed (graceful fallback).
    """
    if not config.meeting_schedule:
        return True
    try:
        parsed = parse_pattern(config.meeting_schedule)
    except ValueError:
        return True
    dates = set(generate_dates(parsed, d, months=1))
    return d in dates


def generate_meeting_dates(
    config: Configuration, start: date, end: date
) -> Optional[Set[date]]:
    """Return the set of meeting dates in [start, end], or None if unset/malformed.

    Callers treat `None` as "no restriction — every day counts".
    """
    if not config.meeting_schedule:
        return None
    try:
        parsed = parse_pattern(config.meeting_schedule)
    except ValueError:
        return None
    # generate_dates takes start + months; over-generate and filter.
    months = max(1, ((end - start).days // 30) + 2)
    candidates = generate_dates(parsed, start, months=months)
    return {d for d in candidates if start <= d <= end}


def align_matches_schedule(
    host_pattern: str, config: Configuration, start: date
) -> Tuple[bool, Optional[str]]:
    """Check whether a host's recurring pattern aligns with meeting_schedule.

    Returns `(True, None)` when the schedule is unset or when every date the
    host's pattern generates over the next 3 months is also a meeting day.
    Returns `(False, reason)` when the host's pattern has no dates, is
    unparseable, or generates dates that are not meeting days.
    """
    if not config.meeting_schedule:
        return True, None
    try:
        host_parsed = parse_pattern(host_pattern)
    except ValueError:
        return False, f"Pattern `{host_pattern}` is not recognized."

    meeting = generate_meeting_dates(config, start, start.replace(year=start.year + 1))
    if meeting is None:
        # Malformed meeting_schedule — treat as unset (graceful).
        return True, None

    host_dates = set(generate_dates(host_parsed, start, months=3))
    if not host_dates:
        return False, (
            f"Pattern `{host_pattern}` generates no dates in the next 3 months."
        )

    off_schedule = host_dates - meeting
    if off_schedule:
        return False, (
            f"Pattern `{host_pattern}` includes dates the exchange does not meet. "
            f"Meeting schedule: `{config.meeting_schedule}`."
        )
    return True, None
