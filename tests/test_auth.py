from __future__ import annotations

from unittest.mock import MagicMock

import discord
import pytest

from src.models.models import Configuration
from src.utils.auth import HARDCODED_OWNER_IDS, is_admin, is_host, is_member, is_owner


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
        member_role_ids=[100],
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


def test_member_role_does_not_grant_admin(config):
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


def test_member_only_is_not_host(config):
    user = make_member(1, role_ids=[100])
    assert is_host(user, config) is False


def test_owner_is_host(config):
    user = make_member(999)
    assert is_host(user, config) is True


# -- is_member --

def test_member_role_grants_member(config):
    user = make_member(1, role_ids=[100])
    assert is_member(user, config) is True


def test_host_role_grants_member(config):
    user = make_member(1, role_ids=[200])
    assert is_member(user, config) is True


def test_admin_role_grants_member(config):
    user = make_member(1, role_ids=[300])
    assert is_member(user, config) is True


def test_no_roles_is_not_member(config):
    user = make_member(1, role_ids=[])
    assert is_member(user, config) is False


def test_owner_is_member(config):
    user = make_member(999)
    assert is_member(user, config) is True


def test_multiple_roles_with_any_match(config):
    user = make_member(1, role_ids=[50, 100, 400])
    assert is_member(user, config) is True
    assert is_host(user, config) is False
