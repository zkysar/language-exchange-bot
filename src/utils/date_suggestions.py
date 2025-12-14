"""Helpers for building date autocomplete suggestions."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from src.utils.date_parser import format_date_short

Suggestion = Tuple[str, date, Optional[Mapping[str, Any]]]


def _normalize_current(current: str) -> str:
    """Normalize autocomplete input for comparison."""
    return current.strip().lower() if current else ""


def _matches_filter(normalized: str, value: str, terms: Sequence[str]) -> bool:
    """
    Determine whether a suggestion should be included based on the user's input.

    Args:
        normalized: Lowercased search string provided by the user
        value: Canonical date string (YYYY-MM-DD)
        terms: Additional terms that should be considered during filtering

    Returns:
        True if the suggestion matches the filter, False otherwise.
    """
    if not normalized:
        return True

    value_lower = value.lower()
    if normalized in value_lower:
        return True

    for term in terms:
        if term and normalized in term.lower():
            return True
    return False


def build_unassigned_date_suggestions(
    events_data: Optional[Mapping[str, Mapping[str, Any]]],
    today: date,
    current: str = "",
    limit: int = 25,
    fallback_days: int = 120,
) -> List[Suggestion]:
    """
    Build suggestions for unassigned future dates (used by /volunteer).

    Args:
        events_data: Cached events dictionary keyed by YYYY-MM-DD strings
        today: Reference date (typically current PST date)
        current: User's current autocomplete input
        limit: Maximum number of suggestions to return
        fallback_days: Days ahead to consider when generating fallback dates

    Returns:
        List of suggestion tuples (date string, date object, event data or None)
    """
    events = events_data or {}
    normalized = _normalize_current(current)
    suggestions: List[Suggestion] = []
    used_values: set[str] = set()

    for date_str in sorted(events.keys()):
        try:
            event_date = date.fromisoformat(date_str)
        except ValueError:
            continue

        if event_date < today:
            continue

        event = events.get(date_str) or {}
        host_id = event.get("host_discord_id")
        if host_id:
            continue

        terms = [format_date_short(event_date), "unassigned"]
        if not _matches_filter(normalized, date_str, terms):
            continue

        suggestions.append((date_str, event_date, event if event else None))
        used_values.add(date_str)

        if len(suggestions) >= limit:
            return suggestions

    if len(suggestions) >= limit:
        return suggestions[:limit]

    # Fallback: suggest future dates even if they are not present in events data
    horizon = today + timedelta(days=fallback_days)
    current_date = today

    while current_date <= horizon and len(suggestions) < limit:
        value = current_date.isoformat()
        if value in used_values:
            current_date += timedelta(days=1)
            continue

        event = events.get(value) or {}
        if event.get("host_discord_id"):
            current_date += timedelta(days=1)
            continue

        terms = [format_date_short(current_date), "unassigned", "available"]
        if not _matches_filter(normalized, value, terms):
            current_date += timedelta(days=1)
            continue

        suggestions.append((value, current_date, None))
        used_values.add(value)
        current_date += timedelta(days=1)

    return suggestions[:limit]


def build_user_assignment_suggestions(
    events_data: Optional[Mapping[str, Mapping[str, Any]]],
    today: date,
    target_user_id: Optional[str],
    current: str = "",
    limit: int = 25,
) -> List[Suggestion]:
    """
    Build suggestions for dates where a specific user is assigned (used by /unvolunteer).

    Args:
        events_data: Cached events dictionary keyed by YYYY-MM-DD strings
        today: Reference date (typically current PST date)
        target_user_id: Discord ID string for the user whose assignments we need
        current: User's current autocomplete input
        limit: Maximum number of suggestions to return

    Returns:
        List of suggestion tuples (date string, date object, event data)
    """
    if not target_user_id:
        return []

    events = events_data or {}
    normalized = _normalize_current(current)
    suggestions: List[Suggestion] = []

    for date_str in sorted(events.keys()):
        try:
            event_date = date.fromisoformat(date_str)
        except ValueError:
            continue

        if event_date < today:
            continue

        event = events.get(date_str) or {}
        host_raw = event.get("host_discord_id")
        if host_raw is None:
            continue

        host_id = str(host_raw).strip()
        if host_id != target_user_id:
            continue

        terms = [format_date_short(event_date), host_id]
        host_username = event.get("host_username")
        if host_username:
            terms.append(str(host_username))

        if not _matches_filter(normalized, date_str, terms):
            continue

        suggestions.append((date_str, event_date, event))

        if len(suggestions) >= limit:
            break

    return suggestions[:limit]


def build_schedule_date_suggestions(
    events_data: Optional[Mapping[str, Mapping[str, Any]]],
    today: date,
    current: str = "",
    limit: int = 25,
    fallback_days: int = 120,
) -> List[Suggestion]:
    """
    Build suggestions for schedule lookup (used by /schedule).

    Args:
        events_data: Cached events dictionary keyed by YYYY-MM-DD strings
        today: Reference date (typically current PST date)
        current: User's current autocomplete input
        limit: Maximum number of suggestions to return
        fallback_days: Days ahead to consider when generating fallback dates

    Returns:
        List of suggestion tuples (date string, date object, event data or None)
    """
    events = events_data or {}
    normalized = _normalize_current(current)
    suggestions: List[Suggestion] = []
    used_values: set[str] = set()

    for date_str in sorted(events.keys()):
        try:
            event_date = date.fromisoformat(date_str)
        except ValueError:
            continue

        if event_date < today:
            continue

        event = events.get(date_str) or {}
        host_username = event.get("host_username")
        host_id = event.get("host_discord_id")
        status_term = str(host_username or host_id or "unassigned")

        terms = [format_date_short(event_date), status_term]
        if not _matches_filter(normalized, date_str, terms):
            continue

        suggestions.append((date_str, event_date, event))
        used_values.add(date_str)

        if len(suggestions) >= limit:
            return suggestions

    if len(suggestions) >= limit:
        return suggestions[:limit]

    # Fallback: offer upcoming dates even if no schedule data exists yet
    horizon = today + timedelta(days=fallback_days)
    current_date = today

    while current_date <= horizon and len(suggestions) < limit:
        value = current_date.isoformat()
        if value in used_values:
            current_date += timedelta(days=1)
            continue

        terms = [format_date_short(current_date)]
        if not _matches_filter(normalized, value, terms):
            current_date += timedelta(days=1)
            continue

        suggestions.append((value, current_date, None))
        used_values.add(value)
        current_date += timedelta(days=1)

    return suggestions[:limit]
