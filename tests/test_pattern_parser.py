from __future__ import annotations

from datetime import date

import pytest

from src.utils.pattern_parser import ParsedPattern, generate_dates, parse_pattern

# -- parse_pattern --

def test_parse_weekly_monday():
    p = parse_pattern("every monday")
    assert p.kind == "weekly"
    assert p.weekday == 0


def test_parse_weekly_sunday():
    p = parse_pattern("every sunday")
    assert p.kind == "weekly"
    assert p.weekday == 6


def test_parse_nth_weekday_first_tuesday():
    p = parse_pattern("every first tuesday")
    assert p.kind == "nth_weekday"
    assert p.weekday == 1
    assert p.nth == 1


def test_parse_nth_weekday_last_friday():
    p = parse_pattern("every last friday")
    assert p.kind == "nth_weekday"
    assert p.weekday == 4
    assert p.nth == -1


def test_parse_nth_weekday_second_wednesday():
    p = parse_pattern("every 2nd wednesday")
    assert p.kind == "nth_weekday"
    assert p.weekday == 2
    assert p.nth == 2


def test_parse_biweekly_keyword():
    p = parse_pattern("biweekly tuesday")
    assert p.kind == "biweekly"
    assert p.weekday == 1


def test_parse_every_other_keyword():
    p = parse_pattern("every other friday")
    assert p.kind == "biweekly"
    assert p.weekday == 4


def test_parse_monthly_plain():
    p = parse_pattern("monthly")
    assert p.kind == "monthly"
    assert p.day_of_month == 1


def test_parse_monthly_every_month():
    p = parse_pattern("every month")
    assert p.kind == "monthly"


def test_parse_monthly_on_the_nth():
    p = parse_pattern("monthly on the 15")
    assert p.kind == "monthly"
    assert p.day_of_month == 15


def test_parse_preserves_original_description():
    p = parse_pattern("Every Monday")
    assert p.description == "Every Monday"


def test_parse_invalid_raises():
    with pytest.raises(ValueError):
        parse_pattern("whenever I feel like it")


def test_parse_invalid_empty_raises():
    with pytest.raises(ValueError):
        parse_pattern("")


# -- generate_dates --

def test_generate_weekly_mondays():
    p = ParsedPattern(kind="weekly", weekday=0)
    start = date(2025, 1, 1)  # Wed
    dates = generate_dates(p, start, months=1)
    # Mondays between 2025-01-01 and 2025-02-01
    assert date(2025, 1, 6) in dates
    assert date(2025, 1, 13) in dates
    assert date(2025, 1, 20) in dates
    assert date(2025, 1, 27) in dates
    # All returned dates are Mondays
    assert all(d.weekday() == 0 for d in dates)


def test_generate_biweekly_spacing():
    p = ParsedPattern(kind="biweekly", weekday=2)  # Wednesday
    start = date(2025, 1, 1)
    dates = generate_dates(p, start, months=3)
    assert all(d.weekday() == 2 for d in dates)
    # Gaps of 14 days
    for a, b in zip(dates, dates[1:]):
        assert (b - a).days == 14


def test_generate_nth_weekday_first_monday():
    p = ParsedPattern(kind="nth_weekday", weekday=0, nth=1)
    start = date(2025, 1, 1)
    dates = generate_dates(p, start, months=3)
    # first Monday of Jan 2025 = 6, Feb = 3, Mar = 3
    assert date(2025, 1, 6) in dates
    assert date(2025, 2, 3) in dates
    assert date(2025, 3, 3) in dates


def test_generate_nth_weekday_last_friday():
    p = ParsedPattern(kind="nth_weekday", weekday=4, nth=-1)
    start = date(2025, 1, 1)
    dates = generate_dates(p, start, months=3)
    # Last Friday of Jan 2025 = 31, Feb = 28, Mar = 28
    assert date(2025, 1, 31) in dates
    assert date(2025, 2, 28) in dates
    assert date(2025, 3, 28) in dates


def test_generate_monthly_on_the_15th():
    p = ParsedPattern(kind="monthly", day_of_month=15)
    start = date(2025, 1, 1)
    dates = generate_dates(p, start, months=3)
    assert date(2025, 1, 15) in dates
    assert date(2025, 2, 15) in dates
    assert date(2025, 3, 15) in dates


def test_generate_monthly_on_31st_skips_short_months():
    p = ParsedPattern(kind="monthly", day_of_month=31)
    start = date(2025, 1, 1)
    dates = generate_dates(p, start, months=3)
    # Feb has no 31st
    assert date(2025, 1, 31) in dates
    assert date(2025, 3, 31) in dates
    assert not any(d.month == 2 for d in dates)


def test_generate_dates_bounded_by_months():
    p = ParsedPattern(kind="weekly", weekday=0)
    start = date(2025, 1, 1)
    dates = generate_dates(p, start, months=1)
    # Nothing far into the future
    assert all(d <= date(2025, 3, 1) for d in dates)


def test_generate_dates_not_before_start():
    p = ParsedPattern(kind="weekly", weekday=0)
    start = date(2025, 1, 8)  # Wed — first Monday after is Jan 13
    dates = generate_dates(p, start, months=1)
    assert all(d >= start for d in dates)


def test_parse_then_generate_roundtrip_every_monday():
    p = parse_pattern("every monday")
    dates = generate_dates(p, date(2025, 6, 1), months=1)
    assert len(dates) >= 4
    assert all(d.weekday() == 0 for d in dates)
