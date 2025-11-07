"""Consistent error handling utilities for Discord commands."""

import logging
from typing import Any, Optional

import discord
from gspread.exceptions import APIError

from src.utils.logger import log_with_context, sanitize_log_data


async def send_error_response(
    interaction: discord.Interaction,
    user_message: str,
    logger: logging.Logger,
    error: Optional[Exception] = None,
    context: Optional[dict[str, Any]] = None,
    ephemeral: bool = True,
) -> None:
    """
    Send consistent error response to Discord user and log technical details.

    Args:
        interaction: Discord interaction to respond to
        user_message: User-friendly error message (no technical details)
        logger: Logger instance for technical logging
        error: Exception that occurred (optional)
        context: Additional context dictionary for logging
        ephemeral: Whether response should be ephemeral (default: True)
    """
    # Sanitize context before logging
    sanitized_context = sanitize_log_data(context) if context else {}

    # Add error details to context
    if error:
        sanitized_context["error_type"] = type(error).__name__
        sanitized_context["error_message"] = str(error)

    # Log technical details
    log_with_context(
        logger,
        "error",
        f"Command error: {user_message}",
        sanitized_context,
    )

    # Log full exception if present
    if error:
        logger.exception("Exception details", exc_info=error)

    # Send user-friendly message
    try:
        if interaction.response.is_done():
            await interaction.followup.send(f"❌ {user_message}", ephemeral=ephemeral)
        else:
            await interaction.response.send_message(f"❌ {user_message}", ephemeral=ephemeral)
    except Exception as send_error:
        logger.error(f"Failed to send error response: {send_error}", exc_info=True)


async def handle_api_error(
    interaction: discord.Interaction,
    error: APIError,
    logger: logging.Logger,
    operation: str,
    context: Optional[dict[str, Any]] = None,
) -> None:
    """
    Handle Google Sheets API errors with user-friendly messages.

    Args:
        interaction: Discord interaction to respond to
        error: APIError exception
        logger: Logger instance
        operation: Description of operation that failed
        context: Additional context dictionary
    """
    error_code = error.response.status_code if hasattr(error, "response") else "unknown"

    # Determine user-friendly message based on error code
    if error_code == 429:
        user_message = (
            "Google Sheets API rate limit exceeded. " "Please try again in a few minutes."
        )
    elif error_code == 403:
        user_message = (
            "Google Sheets API access denied. " "Please check service account permissions."
        )
    elif error_code == 404:
        user_message = "Google Sheets spreadsheet not found. " "Please check configuration."
    else:
        user_message = f"Google Sheets API error occurred during {operation}."

    # Add API error details to context
    api_context = {
        **(context or {}),
        "operation": operation,
        "api_error_code": error_code,
    }

    await send_error_response(interaction, user_message, logger, error, api_context)


def get_command_context(
    interaction: discord.Interaction, command_name: str, **kwargs
) -> dict[str, Any]:
    """
    Build standardized context dictionary for command logging.

    Args:
        interaction: Discord interaction
        command_name: Name of command
        **kwargs: Additional context fields

    Returns:
        Context dictionary with sanitized data
    """
    context = {
        "command": command_name,
        "user_id": str(interaction.user.id),
        "user_name": interaction.user.name,
        "guild_id": str(interaction.guild.id) if interaction.guild else None,
        "channel_id": str(interaction.channel.id) if interaction.channel else None,
        **kwargs,
    }

    return sanitize_log_data(context)
