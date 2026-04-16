from __future__ import annotations

from datetime import date

from src.models.models import Configuration
from src.utils.meeting_schedule import (
    align_matches_schedule,
    generate_meeting_dates,
    is_meeting_day,
)


def _cfg(schedule: str | None) -> Configuration:
    cfg = Configuration.default()
    cfg.meeting_schedule = schedule
    return cfg


# ── is_meeting_day ────────────────────────────────────────────────────────────

def test_is_meeting_day_unset_returns_true_for_any_day():
    cfg = _cfg(None)
    assert is_meeting_day(date(2026, 4, 15), cfg) is True  # Wednesday
    assert is_meeting_day(date(2026, 4, 16), cfg) is True  # Thursday
    assert is_meeting_day(date(2026, 4, 18), cfg) is True  # Saturday


def test_is_meeting_day_weekly_matches_only_that_weekday():
    cfg = _cfg("every wednesday")
    assert is_meeting_day(date(2026, 4, 15), cfg) is True   # Wednesday
    assert is_meeting_day(date(2026, 4, 16), cfg) is False  # Thursday


def test_is_meeting_day_nth_weekday_matches_only_that_nth():
    cfg = _cfg("every 2nd tuesday")
    # April 2026: 7th, 14th, 21st, 28th. The 14th is the 2nd Tuesday.
    assert is_meeting_day(date(2026, 4, 14), cfg) is True
    assert is_meeting_day(date(2026, 4, 7), cfg) is False
    assert is_meeting_day(date(2026, 4, 21), cfg) is False


def test_is_meeting_day_malformed_schedule_returns_true():
    cfg = _cfg("not a real pattern")
    # Graceful fallback: invalid schedule = allow any date
    assert is_meeting_day(date(2026, 4, 15), cfg) is True


# ── generate_meeting_dates ────────────────────────────────────────────────────

def test_generate_meeting_dates_unset_returns_none():
    cfg = _cfg(None)
    assert generate_meeting_dates(cfg, date(2026, 4, 1), date(2026, 5, 1)) is None


def test_generate_meeting_dates_weekly_returns_only_weekdays():
    cfg = _cfg("every wednesday")
    dates = generate_meeting_dates(cfg, date(2026, 4, 1), date(2026, 4, 30))
    assert dates is not None
    for d in dates:
        assert d.weekday() == 2  # Wednesday
    # April 2026 has Wednesdays on the 1st, 8th, 15th, 22nd, 29th
    assert date(2026, 4, 1) in dates
    assert date(2026, 4, 29) in dates


def test_generate_meeting_dates_malformed_returns_none():
    cfg = _cfg("total garbage")
    assert generate_meeting_dates(cfg, date(2026, 4, 1), date(2026, 5, 1)) is None


# ── align_matches_schedule ────────────────────────────────────────────────────

def test_align_unset_schedule_any_pattern_aligns():
    cfg = _cfg(None)
    ok, _ = align_matches_schedule("every tuesday", cfg, date(2026, 4, 1))
    assert ok is True


def test_align_same_pattern_aligns():
    cfg = _cfg("every wednesday")
    ok, _ = align_matches_schedule("every wednesday", cfg, date(2026, 4, 1))
    assert ok is True


def test_align_subset_pattern_aligns():
    # host: biweekly wednesday; schedule: every wednesday
    # all biweekly wednesdays are wednesdays — subset, aligns
    cfg = _cfg("every wednesday")
    ok, _ = align_matches_schedule("biweekly wednesday", cfg, date(2026, 4, 1))
    assert ok is True


def test_align_disjoint_pattern_blocked():
    cfg = _cfg("every wednesday")
    ok, reason = align_matches_schedule("every tuesday", cfg, date(2026, 4, 1))
    assert ok is False
    assert reason  # human-readable reason string


def test_align_host_broader_than_schedule_blocked():
    # schedule: biweekly wednesday; host wants every wednesday
    # host's set includes wednesdays that are NOT meeting days (alternate weeks)
    cfg = _cfg("biweekly wednesday")
    ok, reason = align_matches_schedule("every wednesday", cfg, date(2026, 4, 1))
    assert ok is False
    assert reason


def test_align_unparseable_host_pattern_blocked():
    cfg = _cfg("every wednesday")
    ok, reason = align_matches_schedule("total nonsense", cfg, date(2026, 4, 1))
    assert ok is False
    assert reason
