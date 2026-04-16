import os
from typing import FrozenSet, Iterable, Set

import discord

_DEFAULT_OWNER_IDS: FrozenSet[int] = frozenset({166793917461692416})


def _load_hardcoded_owners() -> FrozenSet[int]:
    """Resolve the bootstrap owner set, allowing env override for rotation."""
    env = os.environ.get("BOT_OWNER_IDS")
    if env is None:
        return _DEFAULT_OWNER_IDS
    ids: set[int] = set()
    for raw in env.split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            ids.add(int(raw))
        except ValueError:
            continue
    return frozenset(ids)


HARDCODED_OWNER_IDS: FrozenSet[int] = _load_hardcoded_owners()


def _user_role_ids(user: discord.abc.User) -> Set[int]:
    if isinstance(user, discord.Member):
        return {r.id for r in user.roles}
    return set()


def _overlap(user_ids: Set[int], allowed: Iterable) -> bool:
    try:
        allowed_ints = {int(x) for x in allowed}
    except (TypeError, ValueError):
        return False
    return bool(user_ids & allowed_ints)


def is_owner(user: discord.abc.User, config) -> bool:
    uid = int(user.id)
    if uid in HARDCODED_OWNER_IDS:
        return True
    try:
        owners = {int(x) for x in getattr(config, "owner_user_ids", []) or []}
    except (TypeError, ValueError):
        return False
    return uid in owners


def is_admin(user: discord.abc.User, config) -> bool:
    if is_owner(user, config):
        return True
    return _overlap(_user_role_ids(user), config.admin_role_ids)


def is_host(user: discord.abc.User, config) -> bool:
    if is_owner(user, config):
        return True
    ids = _user_role_ids(user)
    return _overlap(ids, config.admin_role_ids) or _overlap(ids, config.host_role_ids)


def is_member(user: discord.abc.User, config) -> bool:
    if is_owner(user, config):
        return True
    ids = _user_role_ids(user)
    return (
        _overlap(ids, config.admin_role_ids)
        or _overlap(ids, config.host_role_ids)
        or _overlap(ids, config.member_role_ids)
    )
