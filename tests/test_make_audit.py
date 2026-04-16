from __future__ import annotations

from datetime import date

from src.services.sheets_service import make_audit


def test_make_audit_required_fields():
    entry = make_audit("volunteer", "42")
    assert entry.action_type == "volunteer"
    assert entry.user_discord_id == "42"
    assert entry.outcome == "success"
    assert entry.error_message is None
    assert entry.metadata == {}
    assert entry.entry_id  # uuid string
    assert entry.timestamp is not None


def test_make_audit_unique_ids():
    a = make_audit("x", "1")
    b = make_audit("x", "1")
    assert a.entry_id != b.entry_id


def test_make_audit_all_optional_fields():
    entry = make_audit(
        "unvolunteer",
        "42",
        target_user_discord_id="99",
        event_date=date(2025, 1, 1),
        recurring_pattern_id="p1",
        outcome="failure",
        error_message="oops",
        metadata={"foo": "bar"},
    )
    assert entry.target_user_discord_id == "99"
    assert entry.event_date == date(2025, 1, 1)
    assert entry.recurring_pattern_id == "p1"
    assert entry.outcome == "failure"
    assert entry.error_message == "oops"
    assert entry.metadata == {"foo": "bar"}


def test_make_audit_defaults_metadata_when_none():
    entry = make_audit("x", "1", metadata=None)
    assert entry.metadata == {}


def test_make_audit_timestamp_uses_utc():
    entry = make_audit("x", "1")
    assert entry.timestamp.tzinfo is not None
