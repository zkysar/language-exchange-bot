from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.models.models import Configuration
from src.services.discord_service import should_post_schedule

LA = ZoneInfo("America/Los_Angeles")
UTC = ZoneInfo("UTC")


def _now(hour: int, minute: int = 0, *, day: int = 15) -> datetime:
    return datetime(2026, 4, day, hour, minute, tzinfo=LA)


def _cfg(**overrides) -> Configuration:
    base = dict(
        schedule_announcement_interval_days=30,
        schedule_announcement_lookahead_weeks=4,
        daily_check_time="09:00",
        daily_check_timezone="America/Los_Angeles",
    )
    base.update(overrides)
    return Configuration(**base)


def test_disabled_when_interval_none():
    cfg = _cfg(schedule_announcement_interval_days=None)
    assert should_post_schedule(cfg, _now(10), None) is False


def test_disabled_when_lookahead_none():
    cfg = _cfg(schedule_announcement_lookahead_weeks=None)
    assert should_post_schedule(cfg, _now(10), None) is False


def test_disabled_when_daily_check_time_malformed():
    cfg = _cfg(daily_check_time="not-a-time")
    assert should_post_schedule(cfg, _now(10), None) is False


def test_before_daily_check_time_blocks():
    cfg = _cfg(daily_check_time="09:00")
    assert should_post_schedule(cfg, _now(8, 59), None) is False


def test_at_daily_check_time_fires_when_last_at_is_none():
    cfg = _cfg(daily_check_time="09:00")
    assert should_post_schedule(cfg, _now(9, 0), None) is True


def test_after_daily_check_time_fires_when_last_at_is_none():
    cfg = _cfg(daily_check_time="09:00")
    assert should_post_schedule(cfg, _now(12, 0), None) is True


def test_within_interval_blocks():
    cfg = _cfg(schedule_announcement_interval_days=30, daily_check_time="09:00")
    now = _now(10, 0)
    last = now - timedelta(days=29)
    assert should_post_schedule(cfg, now, last) is False


def test_exactly_at_interval_fires():
    cfg = _cfg(schedule_announcement_interval_days=30, daily_check_time="09:00")
    now = _now(10, 0)
    last = now - timedelta(days=30)
    assert should_post_schedule(cfg, now, last) is True


def test_past_interval_fires():
    cfg = _cfg(schedule_announcement_interval_days=7, daily_check_time="09:00")
    now = _now(10, 0)
    last = now - timedelta(days=100)
    assert should_post_schedule(cfg, now, last) is True


def test_mixed_timezones_compare_correctly():
    """last_at may be stored in UTC; should subtract across tz correctly."""
    cfg = _cfg(schedule_announcement_interval_days=7, daily_check_time="09:00")
    now_la = _now(10, 0)  # 17:00 UTC
    last_utc = (now_la - timedelta(days=8)).astimezone(UTC)
    assert should_post_schedule(cfg, now_la, last_utc) is True


def test_minute_just_before_target_blocks():
    cfg = _cfg(daily_check_time="09:30")
    assert should_post_schedule(cfg, _now(9, 29), None) is False


def test_minute_exact_target_fires():
    cfg = _cfg(daily_check_time="09:30")
    assert should_post_schedule(cfg, _now(9, 30), None) is True
