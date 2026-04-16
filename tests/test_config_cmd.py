from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.config_cmd import build_command
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
