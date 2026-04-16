from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.config_cmd import build_group
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


@pytest.fixture
def group(sheets, cache):
    return build_group(sheets, cache)


def test_config_group_has_expected_commands(group):
    names = {cmd.name for cmd in group.commands}
    assert "show" in names
    assert "set" in names
    assert "roles" in names


def test_config_group_name(group):
    assert group.name == "config"
