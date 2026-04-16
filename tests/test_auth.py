from __future__ import annotations

from unittest.mock import MagicMock

import discord
import pytest

from src.models.models import Configuration
from src.utils.auth import (
    HARDCODED_OWNER_IDS,
    _load_hardcoded_owners,
    is_admin,
    is_host,
    is_owner,
)


def make_member(user_id: int, role_ids: list[int] | None = None) -> MagicMock:
    member = MagicMock(spec=discord.Member)
    member.id = user_id
    member.roles = [MagicMock(id=rid) for rid in (role_ids or [])]
    return member


def make_plain_user(user_id: int) -> MagicMock:
    # Not a Member — simulates a user outside a guild
    user = MagicMock(spec=discord.User)
    user.id = user_id
    return user


@pytest.fixture
def config():
    return Configuration(
        host_role_ids=[200],
        admin_role_ids=[300],
        owner_user_ids=[999],
    )


# -- is_owner --

def test_hardcoded_owner_is_owner(config):
    hardcoded = next(iter(HARDCODED_OWNER_IDS))
    user = make_member(hardcoded)
    assert is_owner(user, config) is True


def test_config_owner_is_owner(config):
    user = make_member(999)
    assert is_owner(user, config) is True


def test_non_owner_is_not_owner(config):
    user = make_member(1234)
    assert is_owner(user, config) is False


def test_is_owner_handles_bad_config():
    bad_config = MagicMock()
    bad_config.owner_user_ids = ["not-an-int"]
    user = make_member(5555)
    assert is_owner(user, bad_config) is False


def test_is_owner_handles_none_owner_ids():
    bad_config = MagicMock()
    bad_config.owner_user_ids = None
    user = make_member(5555)
    assert is_owner(user, bad_config) is False


# -- is_admin --

def test_admin_role_grants_admin(config):
    user = make_member(1, role_ids=[300])
    assert is_admin(user, config) is True


def test_unrecognized_role_does_not_grant_admin(config):
    user = make_member(1, role_ids=[100])
    assert is_admin(user, config) is False


def test_owner_is_always_admin(config):
    user = make_member(999)  # listed as owner
    assert is_admin(user, config) is True


def test_plain_user_without_roles_is_not_admin(config):
    user = make_plain_user(1)
    assert is_admin(user, config) is False


# -- is_host --

def test_host_role_grants_host(config):
    user = make_member(1, role_ids=[200])
    assert is_host(user, config) is True


def test_admin_role_grants_host(config):
    user = make_member(1, role_ids=[300])
    assert is_host(user, config) is True


def test_unrecognized_role_is_not_host(config):
    user = make_member(1, role_ids=[100])
    assert is_host(user, config) is False


def test_owner_is_host(config):
    user = make_member(999)
    assert is_host(user, config) is True



# -- _load_hardcoded_owners (env-var override) --

def test_load_hardcoded_owners_default_when_env_unset(monkeypatch):
    monkeypatch.delenv("BOT_OWNER_IDS", raising=False)
    owners = _load_hardcoded_owners()
    assert 166793917461692416 in owners


def test_load_hardcoded_owners_env_replaces_default(monkeypatch):
    monkeypatch.setenv("BOT_OWNER_IDS", "111,222,333")
    owners = _load_hardcoded_owners()
    assert owners == frozenset({111, 222, 333})
    # The original default is no longer present
    assert 166793917461692416 not in owners


def test_load_hardcoded_owners_empty_env_revokes_all(monkeypatch):
    monkeypatch.setenv("BOT_OWNER_IDS", "")
    owners = _load_hardcoded_owners()
    assert owners == frozenset()


def test_load_hardcoded_owners_skips_garbage(monkeypatch):
    monkeypatch.setenv("BOT_OWNER_IDS", "111, not-an-id ,222,")
    owners = _load_hardcoded_owners()
    assert owners == frozenset({111, 222})
