from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.models import Configuration
from src.commands.config_cmd import build_group


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


def test_config_group_has_expected_subgroups(group):
    names = {cmd.name for cmd in group.commands}
    assert "show" in names
    assert "warnings" in names
    assert "schedule" in names
    assert "channels" in names
    assert "roles" in names


def test_config_group_name(group):
    assert group.name == "config"
