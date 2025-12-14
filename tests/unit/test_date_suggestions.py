"""Unit tests for date suggestion helpers."""

from datetime import date

from src.utils.date_suggestions import (
    build_schedule_date_suggestions,
    build_unassigned_date_suggestions,
    build_user_assignment_suggestions,
)


class TestBuildUnassignedDateSuggestions:
    """Tests for unassigned date suggestion helper."""

    def test_unassigned_suggestions_skip_assigned(self):
        """Should include only unassigned future dates."""
        events = {
            "2025-11-02": {"host_discord_id": None},
            "2025-11-03": {"host_discord_id": "123"},  # Assigned, should be skipped
            "2025-11-05": {},  # Empty dict in cache (treated as unassigned)
            "2025-10-15": {},  # Past date, should be ignored
            "invalid-date": {"host_discord_id": None},  # Invalid format, ignored
        }

        today = date(2025, 11, 1)
        suggestions = build_unassigned_date_suggestions(events, today, limit=5)
        values = [value for value, _, _ in suggestions]

        assert "2025-11-02" in values
        assert "2025-11-03" not in values  # assigned
        assert all(date.fromisoformat(value) >= today for value in values[:2])

    def test_unassigned_suggestions_fallback_when_needed(self):
        """Should provide fallback dates when no unassigned events are available."""
        events = {
            "2025-11-02": {"host_discord_id": "456"},  # Assigned date
        }

        today = date(2025, 11, 1)
        suggestions = build_unassigned_date_suggestions(events, today, limit=3)
        values = [value for value, _, _ in suggestions]

        assert values[0] == "2025-11-01"  # Starts from today as fallback
        assert len(values) == 3
        # Assigned dates from events should be skipped during fallback
        assert values == ["2025-11-01", "2025-11-03", "2025-11-04"]

    def test_unassigned_suggestions_filter_with_current_input(self):
        """Filter should restrict results to matching dates or labels."""
        events = {
            "2025-11-10": {},
            "2025-11-20": {},
            "2025-12-05": {},
        }

        today = date(2025, 11, 1)
        suggestions = build_unassigned_date_suggestions(events, today, current="11-20")
        values = [value for value, _, _ in suggestions]

        assert values == ["2025-11-20"]


class TestBuildUserAssignmentSuggestions:
    """Tests for user-specific assignment suggestions."""

    def test_assignment_suggestions_for_target_user(self):
        """Should return only dates assigned to the target user."""
        events = {
            "2025-11-05": {"host_discord_id": "111", "host_username": "alice"},
            "2025-11-06": {"host_discord_id": "222"},
            "2025-10-30": {"host_discord_id": "111"},  # Past date, ignored
            "2025-11-15": {"host_discord_id": "111"},
        }

        today = date(2025, 11, 1)
        suggestions = build_user_assignment_suggestions(events, today, "111")
        values = [value for value, _, _ in suggestions]

        assert values == ["2025-11-05", "2025-11-15"]

    def test_assignment_suggestions_respect_filter(self):
        """Current input filter should be applied to assignments."""
        events = {
            "2025-11-05": {"host_discord_id": "111", "host_username": "alice"},
            "2025-12-05": {"host_discord_id": "111", "host_username": "alice"},
        }

        today = date(2025, 11, 1)
        suggestions = build_user_assignment_suggestions(events, today, "111", current="Dec")
        values = [value for value, _, _ in suggestions]

        assert values == ["2025-12-05"]

    def test_assignment_suggestions_return_empty_for_unknown_user(self):
        """Unknown user should produce no suggestions."""
        events = {
            "2025-11-05": {"host_discord_id": "111"},
        }

        today = date(2025, 11, 1)
        suggestions = build_user_assignment_suggestions(events, today, "999")

        assert suggestions == []


class TestBuildScheduleDateSuggestions:
    """Tests for schedule lookup suggestions."""

    def test_schedule_suggestions_include_status_terms(self):
        """Should include both assigned and unassigned dates."""
        events = {
            "2025-11-05": {"host_discord_id": "111", "host_username": "alice"},
            "2025-11-06": {"host_discord_id": None},
        }

        today = date(2025, 11, 1)
        suggestions = build_schedule_date_suggestions(events, today, limit=3)
        values = [value for value, _, _ in suggestions]

        assert values[:2] == ["2025-11-05", "2025-11-06"]

    def test_schedule_suggestions_fallback_to_future_dates(self):
        """Should provide fallback options when no events exist."""
        events = {}
        today = date(2025, 11, 1)
        suggestions = build_schedule_date_suggestions(events, today, limit=2)
        values = [value for value, _, _ in suggestions]

        assert values == ["2025-11-01", "2025-11-02"]

    def test_schedule_suggestions_filter_by_host(self):
        """Filter should match host username."""
        events = {
            "2025-11-05": {"host_discord_id": "111", "host_username": "alice"},
            "2025-11-06": {"host_discord_id": "222", "host_username": "bob"},
        }

        today = date(2025, 11, 1)
        suggestions = build_schedule_date_suggestions(events, today, current="bob")
        values = [value for value, _, _ in suggestions]

        assert values == ["2025-11-06"]
