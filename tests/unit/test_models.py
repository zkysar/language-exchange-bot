"""Unit tests for model entities."""

from datetime import date

import pytest

from src.models import Configuration, EventDate, Host, RecurringPattern, SettingType


class TestHostModel:
    """Test Host model."""

    def test_create_host_valid(self):
        """Test creating host with valid discord_id."""
        host = Host(discord_id="123456789012345678", discord_username="testuser#1234")
        assert host.discord_id == "123456789012345678"
        assert host.discord_username == "testuser#1234"

    def test_host_invalid_discord_id_short(self):
        """Test creating host with too short discord_id raises ValueError."""
        with pytest.raises(ValueError, match="17-19 digits"):
            Host(discord_id="12345")

    def test_host_invalid_discord_id_non_numeric(self):
        """Test creating host with non-numeric discord_id raises ValueError."""
        with pytest.raises(ValueError, match="must be numeric"):
            Host(discord_id="abcdefghijklmnopqr")

    def test_host_to_dict(self):
        """Test converting host to dictionary."""
        host = Host(discord_id="123456789012345678", discord_username="testuser#1234")
        result = host.to_dict()
        assert result["discord_id"] == "123456789012345678"
        assert result["discord_username"] == "testuser#1234"

    def test_host_from_dict(self):
        """Test creating host from dictionary."""
        data = {
            "discord_id": "123456789012345678",
            "discord_username": "testuser#1234",
        }
        host = Host.from_dict(data)
        assert host.discord_id == "123456789012345678"
        assert host.discord_username == "testuser#1234"


class TestEventDateModel:
    """Test EventDate model."""

    def test_create_event_date_unassigned(self):
        """Test creating unassigned event date."""
        event = EventDate(date=date(2025, 11, 11))
        assert event.date == date(2025, 11, 11)
        assert event.host_discord_id is None
        assert not event.is_assigned()

    def test_create_event_date_assigned(self):
        """Test creating assigned event date."""
        event = EventDate(
            date=date(2025, 11, 11),
            host_discord_id="123456789012345678",
        )
        assert event.is_assigned()

    def test_event_date_invalid_host_id(self):
        """Test creating event date with invalid host_discord_id raises ValueError."""
        with pytest.raises(ValueError, match="17-19 digits"):
            EventDate(date=date(2025, 11, 11), host_discord_id="12345")


class TestRecurringPatternModel:
    """Test RecurringPattern model."""

    def test_create_recurring_pattern(self):
        """Test creating recurring pattern."""
        pattern = RecurringPattern(
            pattern_id="test-pattern-1",
            host_discord_id="123456789012345678",
            pattern_description="every 2nd Tuesday",
            pattern_rule='{"type": "nth_weekday", "nth": 2, "weekday": 1}',
            start_date=date(2025, 11, 11),
        )
        assert pattern.pattern_id == "test-pattern-1"
        assert pattern.is_active

    def test_recurring_pattern_end_date_before_start_raises(self):
        """Test creating pattern with end_date before start_date raises ValueError."""
        with pytest.raises(ValueError, match="end_date must be after start_date"):
            RecurringPattern(
                pattern_id="test-pattern-1",
                host_discord_id="123456789012345678",
                pattern_description="every 2nd Tuesday",
                pattern_rule='{"type": "nth_weekday"}',
                start_date=date(2025, 11, 11),
                end_date=date(2025, 11, 10),  # Before start_date
            )


class TestConfigurationModel:
    """Test Configuration model."""

    def test_create_configuration_string(self):
        """Test creating string configuration."""
        config = Configuration(
            setting_key="test_key",
            setting_value="test_value",
            setting_type=SettingType.STRING,
        )
        assert config.get_typed_value() == "test_value"

    def test_create_configuration_integer(self):
        """Test creating integer configuration."""
        config = Configuration(
            setting_key="cache_ttl_seconds",
            setting_value="300",
            setting_type=SettingType.INTEGER,
        )
        assert config.get_typed_value() == 300

    def test_create_configuration_boolean_true(self):
        """Test creating boolean configuration (true)."""
        config = Configuration(
            setting_key="enabled",
            setting_value="true",
            setting_type=SettingType.BOOLEAN,
        )
        assert config.get_typed_value() is True

    def test_create_configuration_boolean_false(self):
        """Test creating boolean configuration (false)."""
        config = Configuration(
            setting_key="enabled",
            setting_value="false",
            setting_type=SettingType.BOOLEAN,
        )
        assert config.get_typed_value() is False

    def test_create_configuration_json(self):
        """Test creating JSON configuration."""
        config = Configuration(
            setting_key="role_ids",
            setting_value='["123456789012345678", "987654321098765432"]',
            setting_type=SettingType.JSON,
        )
        result = config.get_typed_value()
        assert isinstance(result, list)
        assert len(result) == 2
