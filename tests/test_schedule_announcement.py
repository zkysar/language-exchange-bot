from __future__ import annotations

from datetime import date

from src.models.models import Configuration, EventDate
from src.services.discord_service import build_schedule_lines


def _cfg(meeting_schedule: str | None = None) -> Configuration:
    return Configuration(meeting_schedule=meeting_schedule)


def test_no_meeting_schedule_lists_every_day():
    cfg = _cfg(meeting_schedule=None)
    start = date(2026, 4, 1)  # Wednesday
    lines = build_schedule_lines(cfg, {}, start, lookahead_weeks=1)
    assert lines is not None
    # 7 days + header = 8 lines
    assert len(lines) == 8
    assert "Upcoming schedule" in lines[0]
    # All open
    assert all("*open*" in line for line in lines[1:])


def test_meeting_schedule_filters_to_matching_weekdays():
    cfg = _cfg(meeting_schedule="every wednesday")
    start = date(2026, 4, 1)  # Wednesday
    lines = build_schedule_lines(cfg, {}, start, lookahead_weeks=4)
    assert lines is not None
    # Header + 4 Wednesdays = 5 lines
    assert len(lines) == 5
    for line in lines[1:]:
        assert "*open*" in line


def test_meeting_schedule_no_matches_in_window_returns_none():
    cfg = _cfg(meeting_schedule="every 2nd friday")
    # A 2-week window that deliberately misses the 2nd Friday of the month
    start = date(2026, 4, 13)  # Monday after 2nd Friday (Apr 10)
    # Lookahead=1 week → no 2nd-Friday match (next one is May 8)
    lines = build_schedule_lines(cfg, {}, start, lookahead_weeks=1)
    assert lines is None


def test_assigned_events_render_host_mention_with_discord_id():
    cfg = _cfg(meeting_schedule=None)
    start = date(2026, 4, 1)
    ev = EventDate(date=start, host_discord_id="12345", host_username="alice")
    lines = build_schedule_lines(cfg, {start: ev}, start, lookahead_weeks=1)
    assert lines is not None
    assert any("<@12345>" in line for line in lines[1:])


def test_assigned_events_fallback_to_username_without_id():
    cfg = _cfg(meeting_schedule=None)
    start = date(2026, 4, 1)
    ev = EventDate(date=start, host_discord_id=None, host_username="alice")
    lines = build_schedule_lines(cfg, {start: ev}, start, lookahead_weeks=1)
    assert lines is not None
    # alice appears, not a <@...> mention
    joined = "\n".join(lines[1:])
    assert "alice" in joined
    assert "<@" not in joined


def test_mixed_assigned_and_open():
    cfg = _cfg(meeting_schedule=None)
    start = date(2026, 4, 1)
    ev = EventDate(date=start, host_discord_id="42")
    lines = build_schedule_lines(cfg, {start: ev}, start, lookahead_weeks=1)
    assert lines is not None
    open_count = sum(1 for line in lines[1:] if "*open*" in line)
    assigned_count = sum(1 for line in lines[1:] if "<@42>" in line)
    assert assigned_count == 1
    assert open_count == 6


def test_lookahead_crosses_month_boundary():
    cfg = _cfg(meeting_schedule=None)
    start = date(2026, 4, 28)
    lines = build_schedule_lines(cfg, {}, start, lookahead_weeks=1)
    assert lines is not None
    # 7 days spans Apr 28 -> May 4
    joined = "\n".join(lines)
    # Should mention both months' dates in some form
    assert "Apr" in joined or "04" in joined or "April" in joined
    assert "May" in joined or "05" in joined


def test_empty_events_dict_is_all_open():
    cfg = _cfg(meeting_schedule=None)
    start = date(2026, 4, 1)
    lines = build_schedule_lines(cfg, {}, start, lookahead_weeks=2)
    assert lines is not None
    # 14 days + header
    assert len(lines) == 15
    assert all("*open*" in line for line in lines[1:])
