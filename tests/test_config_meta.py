from __future__ import annotations

import pytest
from src.utils.config_meta import SETTINGS, validate_setting, SettingMeta


def test_all_settings_have_required_fields():
    for key, meta in SETTINGS.items():
        assert isinstance(meta, SettingMeta), f"{key} is not SettingMeta"
        assert meta.group in ("warnings", "schedule", "channels", "roles")
        assert meta.label
        assert meta.config_key
        assert meta.setting_type in ("integer", "time", "timezone", "channel")


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
