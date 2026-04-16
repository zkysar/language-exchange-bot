from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.config_cmd import KEY_CHOICES, build_command
from src.models.models import Configuration


@pytest.fixture
def sheets():
    return MagicMock()


@pytest.fixture
def cache():
    c = MagicMock()
    c.config = Configuration.default()
    c.refresh = AsyncMock()
    return c


def test_config_command_name(sheets, cache):
    cmd = build_command(sheets, cache)
    assert cmd.name == "config"


def test_config_command_has_expected_params(sheets, cache):
    cmd = build_command(sheets, cache)
    param_names = set(cmd._params.keys())
    assert "action" in param_names
    assert "key" in param_names
    assert "value" in param_names


def test_meeting_schedule_key_choice_label_includes_example():
    mp_choice = next((c for c in KEY_CHOICES if c.value == "meeting_schedule"), None)
    assert mp_choice is not None
    assert 'every wednesday' in mp_choice.name.lower()
