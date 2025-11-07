"""Unit tests for date_parser utility."""

from datetime import date, timedelta

import pytest

from src.utils.date_parser import (
    format_date_pst,
    get_current_date_pst,
    parse_date,
    validate_date_format_and_future,
    validate_future_date,
)


class TestParseDateValidFormat:
    """Test parse_date with valid date formats."""

    def test_parse_valid_date(self):
        """Test parsing valid YYYY-MM-DD format."""
        result = parse_date("2025-11-11")
        assert result == date(2025, 11, 11)

    def test_parse_another_valid_date(self):
        """Test parsing another valid date."""
        result = parse_date("2026-01-15")
        assert result == date(2026, 1, 15)


class TestParseDateInvalidFormat:
    """Test parse_date with invalid date formats."""

    def test_parse_invalid_format_mmddyyyy(self):
        """Test parsing MM/DD/YYYY format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            parse_date("11/11/2025")

    def test_parse_invalid_format_ddmmyyyy(self):
        """Test parsing DD-MM-YYYY format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            parse_date("11-11-2025")

    def test_parse_invalid_date(self):
        """Test parsing invalid date raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            parse_date("2025-13-01")  # Month 13 doesn't exist

    def test_parse_empty_string(self):
        """Test parsing empty string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            parse_date("")


class TestValidateFutureDate:
    """Test validate_future_date."""

    def test_validate_future_date_valid(self):
        """Test validating a future date passes."""
        future_date = get_current_date_pst() + timedelta(days=7)
        # Should not raise
        validate_future_date(future_date)

    def test_validate_today_raises(self):
        """Test validating today's date raises ValueError."""
        today = get_current_date_pst()
        with pytest.raises(ValueError, match="Date must be in the future"):
            validate_future_date(today)

    def test_validate_past_date_raises(self):
        """Test validating past date raises ValueError."""
        past_date = get_current_date_pst() - timedelta(days=1)
        with pytest.raises(ValueError, match="Date must be in the future"):
            validate_future_date(past_date)


class TestFormatDatePST:
    """Test format_date_pst."""

    def test_format_date(self):
        """Test formatting date as human-readable string."""
        test_date = date(2025, 11, 11)
        result = format_date_pst(test_date)
        # Should contain day of week, month name, day, year, and PST
        assert "Tuesday" in result
        assert "November" in result
        assert "11" in result
        assert "2025" in result
        assert "PST" in result


class TestGetCurrentDatePST:
    """Test get_current_date_pst."""

    def test_get_current_date(self):
        """Test getting current date in PST."""
        result = get_current_date_pst()
        assert isinstance(result, date)
        # Should be close to today (within 1 day to account for timezone)
        today = date.today()
        diff = abs((result - today).days)
        assert diff <= 1
