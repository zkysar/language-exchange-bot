from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from src.utils import date_parser
from src.utils.date_parser import (
    LA_TZ,
    format_date,
    format_display,
    is_future,
    now_la,
    parse_iso_date,
    today_la,
)


def test_today_la_returns_date_in_la_tz():
    d = today_la()
    assert isinstance(d, date)


def test_now_la_is_tz_aware():
    n = now_la()
    assert n.tzinfo is not None
    assert str(n.tzinfo) == "America/Los_Angeles"


def test_la_tz_name():
    assert str(LA_TZ) == "America/Los_Angeles"


def test_parse_iso_date_valid():
    assert parse_iso_date("2025-01-15") == date(2025, 1, 15)


def test_parse_iso_date_invalid_raises():
    with pytest.raises(ValueError):
        parse_iso_date("not-a-date")


def test_parse_iso_date_wrong_format_raises():
    with pytest.raises(ValueError):
        parse_iso_date("01/15/2025")


def test_format_date_roundtrip():
    d = date(2025, 6, 1)
    assert format_date(d) == "2025-06-01"
    assert parse_iso_date(format_date(d)) == d


def test_format_display_structure():
    d = date(2025, 1, 1)  # Wednesday
    s = format_display(d)
    assert "Jan" in s
    assert "2025" in s
    assert "01" in s


def test_is_future_today_is_true():
    with patch.object(date_parser, "today_la", return_value=date(2025, 6, 15)):
        assert is_future(date(2025, 6, 15)) is True


def test_is_future_tomorrow_is_true():
    with patch.object(date_parser, "today_la", return_value=date(2025, 6, 15)):
        assert is_future(date(2025, 6, 16)) is True


def test_is_future_yesterday_is_false():
    with patch.object(date_parser, "today_la", return_value=date(2025, 6, 15)):
        assert is_future(date(2025, 6, 14)) is False


def test_now_la_and_today_la_agree_within_a_day():
    # Within a reasonable clock skew, today_la should match now_la().date()
    n = now_la()
    t = today_la()
    assert abs((n.date() - t).days) <= 1
    assert (n.date() - t) != timedelta(days=2)
