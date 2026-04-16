from __future__ import annotations

import time
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.models.models import Configuration, EventDate, RecurringPattern
from src.services.cache_service import CacheService


@pytest.fixture
def sheets():
    s = MagicMock()
    s.load_configuration.return_value = Configuration.default()
    s.load_schedule.return_value = []
    s.load_patterns.return_value = []
    return s


@pytest.fixture
def cache(sheets):
    return CacheService(sheets)


def test_config_returns_default_when_unset(cache):
    cfg = cache.config
    assert isinstance(cfg, Configuration)
    assert cfg.warning_passive_days == 4


def test_upsert_event_inserts_and_updates(cache):
    e1 = EventDate(date=date(2025, 1, 1), host_discord_id="alice")
    cache.upsert_event(e1)
    assert cache.get_event(date(2025, 1, 1)) is e1

    e2 = EventDate(date=date(2025, 1, 1), host_discord_id="bob")
    cache.upsert_event(e2)
    assert cache.get_event(date(2025, 1, 1)).host_discord_id == "bob"


def test_all_events_returns_list(cache):
    cache.upsert_event(EventDate(date=date(2025, 1, 1)))
    cache.upsert_event(EventDate(date=date(2025, 1, 2)))
    assert len(cache.all_events()) == 2


def test_get_event_missing_returns_none(cache):
    assert cache.get_event(date(2099, 1, 1)) is None


def test_remove_event_assignment_clears_host_fields(cache):
    e = EventDate(
        date=date(2025, 1, 1),
        host_discord_id="alice",
        host_username="Alice",
        recurring_pattern_id="p1",
        assigned_at=datetime.now(timezone.utc),
        assigned_by="admin",
    )
    cache.upsert_event(e)
    cache.remove_event_assignment(date(2025, 1, 1))
    cleared = cache.get_event(date(2025, 1, 1))
    assert cleared.host_discord_id is None
    assert cleared.host_username is None
    assert cleared.recurring_pattern_id is None
    assert cleared.assigned_at is None
    assert cleared.assigned_by is None
    assert cleared.is_assigned is False


def test_remove_event_assignment_missing_is_noop(cache):
    # Should not raise
    cache.remove_event_assignment(date(2099, 1, 1))


def test_add_and_deactivate_pattern(cache):
    p = RecurringPattern(
        pattern_id="p1",
        host_discord_id="alice",
        host_username="Alice",
        pattern_description="every monday",
        pattern_rule="weekly:0",
        start_date=date(2025, 1, 1),
    )
    cache.add_pattern(p)
    assert cache.active_patterns_for("alice") == [p]

    cache.deactivate_pattern("p1")
    assert cache.active_patterns_for("alice") == []
    # Still tracked, just inactive
    assert cache._patterns["p1"].is_active is False


def test_deactivate_unknown_pattern_is_noop(cache):
    cache.deactivate_pattern("nonexistent")  # should not raise


def test_active_patterns_for_filters_by_host(cache):
    cache.add_pattern(RecurringPattern(
        pattern_id="p1", host_discord_id="alice", host_username="a",
        pattern_description="", pattern_rule="", start_date=date(2025, 1, 1),
    ))
    cache.add_pattern(RecurringPattern(
        pattern_id="p2", host_discord_id="bob", host_username="b",
        pattern_description="", pattern_rule="", start_date=date(2025, 1, 1),
    ))
    result = cache.active_patterns_for("alice")
    assert len(result) == 1
    assert result[0].pattern_id == "p1"


def test_invalidate_resets_sync_time(cache):
    cache._last_sync = time.time()
    cache.invalidate()
    assert cache._last_sync == 0.0


@pytest.mark.asyncio
async def test_refresh_force_loads_all(cache, sheets):
    sheets.load_configuration.return_value = Configuration(warning_passive_days=7)
    sheets.load_schedule.return_value = [EventDate(date=date(2025, 1, 1))]
    sheets.load_patterns.return_value = [
        RecurringPattern(
            pattern_id="p1", host_discord_id="alice", host_username="a",
            pattern_description="", pattern_rule="", start_date=date(2025, 1, 1),
        )
    ]
    await cache.refresh(force=True)
    assert cache.config.warning_passive_days == 7
    assert len(cache.all_events()) == 1
    assert "p1" in cache._patterns
    sheets.load_configuration.assert_called_once()


@pytest.mark.asyncio
async def test_refresh_respects_ttl_when_not_forced(cache, sheets):
    # Prime cache
    await cache.refresh(force=True)
    sheets.load_configuration.reset_mock()
    sheets.load_schedule.reset_mock()

    # Immediately refresh without force → should skip
    await cache.refresh(force=False)
    sheets.load_configuration.assert_not_called()
    sheets.load_schedule.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_force_ignores_ttl(cache, sheets):
    await cache.refresh(force=True)
    sheets.load_configuration.reset_mock()
    await cache.refresh(force=True)
    sheets.load_configuration.assert_called_once()
