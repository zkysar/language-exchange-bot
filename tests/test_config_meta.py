from __future__ import annotations

from src.models.models import Configuration
from src.utils.config_meta import SETTINGS, SettingMeta, validate_setting


def test_all_settings_have_required_fields():
    for key, meta in SETTINGS.items():
        assert isinstance(meta, SettingMeta), f"{key} is not SettingMeta"
        assert meta.group in ("warnings", "schedule", "channels", "roles")
        assert meta.label
        assert meta.config_key
        assert meta.setting_type in ("integer", "time", "timezone", "channel", "pattern")


def test_validate_integer_in_range():
    ok, val, err = validate_setting("warning_passive_days", "7")
    assert ok is True
    assert val == "7"
    assert err is None


def test_validate_integer_out_of_range():
    ok, val, err = validate_setting("warning_passive_days", "99")
    assert ok is False
    assert "1" in err and "30" in err


def test_validate_integer_not_a_number():
    ok, val, err = validate_setting("warning_passive_days", "abc")
    assert ok is False
    assert "integer" in err.lower()


def test_validate_time_valid():
    ok, val, err = validate_setting("daily_check_time", "09:00")
    assert ok is True


def test_validate_time_invalid():
    ok, val, err = validate_setting("daily_check_time", "25:99")
    assert ok is False


def test_validate_timezone_valid():
    ok, val, err = validate_setting("daily_check_timezone", "America/New_York")
    assert ok is True


def test_validate_timezone_invalid():
    ok, val, err = validate_setting("daily_check_timezone", "Mars/Olympus")
    assert ok is False


def test_validate_unknown_key():
    ok, val, err = validate_setting("nonexistent_key", "foo")
    assert ok is False


def test_meeting_schedule_in_settings():
    assert "meeting_schedule" in SETTINGS
    meta = SETTINGS["meeting_schedule"]
    assert meta.group == "schedule"
    assert meta.setting_type == "pattern"
    assert meta.label == "Meeting schedule"


def test_old_meeting_pattern_key_removed():
    assert "meeting_pattern" not in SETTINGS


def test_validate_meeting_schedule_valid():
    ok, val, err = validate_setting("meeting_schedule", "every wednesday")
    assert ok is True
    assert val == "every wednesday"
    assert err is None


def test_validate_meeting_schedule_valid_nth():
    ok, val, err = validate_setting("meeting_schedule", "every 2nd tuesday")
    assert ok is True


def test_validate_meeting_schedule_invalid():
    ok, val, err = validate_setting("meeting_schedule", "not a real pattern")
    assert ok is False
    assert err is not None


def test_validate_meeting_schedule_empty_clears():
    ok, val, err = validate_setting("meeting_schedule", "")
    assert ok is True
    assert val == ""


def test_configuration_has_single_announcement_channel_field():
    cfg = Configuration.default()
    assert hasattr(cfg, "announcement_channel_id")
    assert cfg.announcement_channel_id is None
    assert not hasattr(cfg, "schedule_channel_id")
    assert not hasattr(cfg, "warnings_channel_id")


def test_config_meta_has_single_announcement_channel_entry():
    assert "announcement_channel_id" in SETTINGS
    assert "schedule_channel_id" not in SETTINGS
    assert "warnings_channel_id" not in SETTINGS
    meta = SETTINGS["announcement_channel_id"]
    assert meta.group == "channels"
    assert meta.setting_type == "channel"
    assert meta.config_key == "announcement_channel_id"
    assert meta.sheets_type == "string"
    assert meta.label == "Announcement channel"
