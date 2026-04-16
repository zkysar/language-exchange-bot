from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.models import Configuration, EventDate
from src.services.warning_service import WarningService


@pytest.fixture
def today():
    return date(2025, 6, 1)


@pytest.fixture
def make_cache(today):
    def _make(events: list[EventDate] | None = None, config: Configuration | None = None):
        cache = MagicMock()
        cache.config = config or Configuration()  # defaults: urgent=1, passive=4
        cache.refresh = AsyncMock()
        cache.all_events.return_value = events or []
        return cache
    return _make


@pytest.mark.asyncio
async def test_no_events_produces_warnings_in_window(make_cache, today):
    cache = make_cache()
    svc = WarningService(cache)
    with patch("src.services.warning_service.today_la", return_value=today):
        items = await svc.check(window_weeks=1)
    # Urgent (≤1 day): today + tomorrow = 2 items
    # Passive (2-4 days): 3 items
    urgent = [i for i in items if i.severity == "urgent"]
    passive = [i for i in items if i.severity == "passive"]
    assert len(urgent) == 2
    assert len(passive) == 3


@pytest.mark.asyncio
async def test_assigned_events_skipped(make_cache, today):
    assigned = EventDate(
        date=today + timedelta(days=1),
        host_discord_id="alice",
    )
    cache = make_cache(events=[assigned])
    svc = WarningService(cache)
    with patch("src.services.warning_service.today_la", return_value=today):
        items = await svc.check(window_weeks=1)
    # The day=1 date was assigned → should not appear
    assert not any(i.event_date == today + timedelta(days=1) for i in items)


@pytest.mark.asyncio
async def test_unassigned_event_still_warns(make_cache, today):
    unassigned = EventDate(date=today + timedelta(days=2))  # no host
    cache = make_cache(events=[unassigned])
    svc = WarningService(cache)
    with patch("src.services.warning_service.today_la", return_value=today):
        items = await svc.check(window_weeks=1)
    dates = [i.event_date for i in items]
    assert today + timedelta(days=2) in dates


@pytest.mark.asyncio
async def test_urgent_severity_bucket(make_cache, today):
    config = Configuration(warning_urgent_days=2, warning_passive_days=5)
    cache = make_cache(config=config)
    svc = WarningService(cache)
    with patch("src.services.warning_service.today_la", return_value=today):
        items = await svc.check(window_weeks=1)
    # Days 0, 1, 2 should be urgent; 3, 4, 5 passive
    severities = {i.days_until: i.severity for i in items}
    assert severities[0] == "urgent"
    assert severities[2] == "urgent"
    assert severities[3] == "passive"
    assert severities[5] == "passive"


@pytest.mark.asyncio
async def test_beyond_passive_window_is_excluded(make_cache, today):
    config = Configuration(warning_urgent_days=1, warning_passive_days=2)
    cache = make_cache(config=config)
    svc = WarningService(cache)
    with patch("src.services.warning_service.today_la", return_value=today):
        items = await svc.check(window_weeks=2)
    # Anything past day 2 should be excluded regardless of horizon
    assert all(i.days_until <= 2 for i in items)


@pytest.mark.asyncio
async def test_refresh_is_called(make_cache):
    cache = make_cache()
    svc = WarningService(cache)
    with patch("src.services.warning_service.today_la", return_value=date(2025, 1, 1)):
        await svc.check(window_weeks=1)
    cache.refresh.assert_awaited()


@pytest.mark.asyncio
async def test_window_weeks_bounds_horizon(make_cache, today):
    config = Configuration(warning_urgent_days=100, warning_passive_days=100)
    cache = make_cache(config=config)
    svc = WarningService(cache)
    with patch("src.services.warning_service.today_la", return_value=today):
        items = await svc.check(window_weeks=1)
    horizon = today + timedelta(weeks=1)
    assert all(today <= i.event_date <= horizon for i in items)
    # 7 days + today = 8 items
    assert len(items) == 8
