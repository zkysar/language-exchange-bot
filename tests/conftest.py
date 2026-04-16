from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.models import Configuration


@pytest.fixture
def cache() -> MagicMock:
    c = MagicMock()
    c.config = Configuration.default()
    c.refresh = AsyncMock()
    c.all_events = MagicMock(return_value=[])
    c.get_event = MagicMock(return_value=None)
    c.upsert_event = MagicMock()
    c.remove_event_assignment = MagicMock()
    c.active_patterns_for = MagicMock(return_value=[])
    c.deactivate_pattern = MagicMock()
    c.add_pattern = MagicMock()
    c.invalidate = MagicMock()
    c.sheets = MagicMock()
    c.sheets.load_schedule = MagicMock()
    return c


@pytest.fixture
def sheets() -> MagicMock:
    s = MagicMock()
    s.write_lock = asyncio.Lock()
    return s
