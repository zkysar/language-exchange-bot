from __future__ import annotations

from datetime import date, datetime

from src.models.models import (
    AuditEntry,
    Configuration,
    EventDate,
    Host,
    RecurringPattern,
)

# -- Host --

def test_host_minimal_construction():
    h = Host(discord_id="123")
    assert h.discord_id == "123"
    assert h.discord_username == ""
    assert h.created_at is None


# -- EventDate --

def test_event_date_unassigned_is_not_assigned():
    e = EventDate(date=date(2025, 1, 1))
    assert e.is_assigned is False


def test_event_date_with_host_is_assigned():
    e = EventDate(date=date(2025, 1, 1), host_discord_id="42")
    assert e.is_assigned is True


def test_event_date_with_empty_host_id_is_not_assigned():
    e = EventDate(date=date(2025, 1, 1), host_discord_id="")
    assert e.is_assigned is False


# -- RecurringPattern --

def test_recurring_pattern_defaults_active():
    p = RecurringPattern(
        pattern_id="p1",
        host_discord_id="42",
        host_username="bob",
        pattern_description="every monday",
        pattern_rule="weekly:0",
        start_date=date(2025, 1, 1),
    )
    assert p.is_active is True
    assert p.end_date is None


# -- AuditEntry --

def test_audit_entry_metadata_defaults_to_empty_dict():
    e = AuditEntry(
        entry_id="e1",
        timestamp=datetime(2025, 1, 1, 12, 0),
        action_type="volunteer",
        user_discord_id="42",
    )
    assert e.metadata == {}
    assert e.outcome == "success"


def test_audit_entry_metadata_independent_instances():
    # Guard against the mutable-default-arg gotcha.
    a = AuditEntry(entry_id="a", timestamp=datetime.now(), action_type="x", user_discord_id="1")
    b = AuditEntry(entry_id="b", timestamp=datetime.now(), action_type="x", user_discord_id="2")
    a.metadata["key"] = "value"
    assert "key" not in b.metadata


# -- Configuration --

def test_configuration_default_sensible_values():
    c = Configuration.default()
    assert c.warning_passive_days == 4
    assert c.warning_urgent_days == 1
    assert c.daily_check_time == "09:00"
    assert c.daily_check_timezone == "America/Los_Angeles"
    assert c.schedule_window_weeks == 2
    assert c.cache_ttl_seconds == 300
    assert c.max_batch_size == 100


def test_configuration_default_has_empty_id_lists():
    c = Configuration.default()
    assert c.member_role_ids == []
    assert c.host_role_ids == []
    assert c.admin_role_ids == []
    assert c.owner_user_ids == []


def test_configuration_default_independent_instances():
    a = Configuration.default()
    b = Configuration.default()
    a.host_role_ids.append(42)
    assert b.host_role_ids == []


def test_configuration_channel_ids_default_none():
    c = Configuration.default()
    assert c.announcement_channel_id is None
