from typing import Iterable, Set

import discord


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


def is_admin(user: discord.abc.User, config) -> bool:
    return _overlap(_user_role_ids(user), config.admin_role_ids)


def is_host(user: discord.abc.User, config) -> bool:
    ids = _user_role_ids(user)
    return _overlap(ids, config.admin_role_ids) or _overlap(ids, config.host_role_ids)


def is_member(user: discord.abc.User, config) -> bool:
    ids = _user_role_ids(user)
    return (
        _overlap(ids, config.admin_role_ids)
        or _overlap(ids, config.host_role_ids)
        or _overlap(ids, config.member_role_ids)
    )
