"""Authorization and role checking utilities."""

import logging
from typing import Optional

import discord

logger = logging.getLogger("discord_host_scheduler.auth")


def has_role_by_id(member: discord.Member, role_ids: list[str]) -> bool:
    """
    Check if Discord member has any of the specified roles by ID.

    Args:
        member: Discord member to check
        role_ids: List of role IDs to check (as strings or integers)

    Returns:
        True if member has any of the roles, False otherwise
    """
    if not role_ids:
        return False

    # Check if this is actually a Member object with roles
    if not isinstance(member, discord.Member):
        logger.error(
            f"User object is not a Member (type: {type(member).__name__}), cannot check roles"
        )
        return False

    # Convert member role IDs to strings
    member_role_ids = {str(role.id) for role in member.roles}

    # Convert configured role IDs to strings (handles both int and str from JSON)
    configured_role_ids = {str(role_id) for role_id in role_ids}

    return bool(member_role_ids & configured_role_ids)


def check_organizer_role(member: discord.Member, organizer_role_ids: list[str]) -> bool:
    """
    Check if member has organizer (admin) role.

    Args:
        member: Discord member to check
        organizer_role_ids: List of organizer role IDs from configuration

    Returns:
        True if member is an organizer, False otherwise
    """
    return has_role_by_id(member, organizer_role_ids)


def check_host_privileged_role(member: discord.Member, host_privileged_role_ids: list[str]) -> bool:
    """
    Check if member has host-privileged role (can volunteer on behalf of others).

    Args:
        member: Discord member to check
        host_privileged_role_ids: List of host-privileged role IDs from configuration

    Returns:
        True if member has host-privileged role, False otherwise
    """
    return has_role_by_id(member, host_privileged_role_ids)


def authorize_proxy_action(
    command_user: discord.Member,
    target_user_id: Optional[str],
    host_privileged_role_ids: list[str],
) -> None:
    """
    Authorize proxy action (volunteering/unvolunteering on behalf of another user).

    Args:
        command_user: Discord member executing the command
        target_user_id: Discord ID of target user (None if same as command user)
        host_privileged_role_ids: List of host-privileged role IDs from configuration

    Raises:
        PermissionError: If user is not authorized to perform proxy action
    """
    # If target_user_id is None or same as command user, no authorization needed
    if target_user_id is None or str(command_user.id) == target_user_id:
        return

    # Check if command user has host-privileged role
    if not check_host_privileged_role(command_user, host_privileged_role_ids):
        raise PermissionError(
            "You do not have permission to volunteer on behalf of other users. "
            "Required role: host-privileged"
        )


def authorize_admin_command(command_user: discord.Member, organizer_role_ids: list[str]) -> None:
    """
    Authorize admin command (sync, warnings, reset).

    Args:
        command_user: Discord member executing the command
        organizer_role_ids: List of organizer role IDs from configuration

    Raises:
        PermissionError: If user is not authorized to execute admin commands
    """
    if not check_organizer_role(command_user, organizer_role_ids):
        raise PermissionError(
            "You do not have permission to execute this command. Required role: organizer"
        )
