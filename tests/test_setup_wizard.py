from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.setup_wizard import build_command
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


def test_setup_command_name(sheets, cache):
    cmd = build_command(sheets, cache)
    assert cmd.name == "setup"


def test_setup_command_description(sheets, cache):
    cmd = build_command(sheets, cache)
    assert "wizard" in cmd.description.lower() or "guided" in cmd.description.lower()
