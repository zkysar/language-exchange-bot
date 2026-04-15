from __future__ import annotations

import asyncio
import time
from datetime import date
from typing import Dict, List, Optional

from src.models.models import Configuration, EventDate, RecurringPattern
from src.services.sheets_service import SheetsService
from src.utils.logger import get_logger

log = get_logger(__name__)


class CacheService:
    def __init__(self, sheets: SheetsService) -> None:
        self.sheets = sheets
        self._lock = asyncio.Lock()
        self._events: Dict[date, EventDate] = {}
        self._patterns: Dict[str, RecurringPattern] = {}
        self._config: Optional[Configuration] = None
        self._last_sync: float = 0.0

    @property
    def config(self) -> Configuration:
        if self._config is None:
            self._config = Configuration.default()
        return self._config

    async def refresh(self, force: bool = False) -> None:
        ttl = self.config.cache_ttl_seconds if self._config else 300
        if not force and (time.time() - self._last_sync) < ttl and self._config:
            return
        async with self._lock:
            loop = asyncio.get_running_loop()
            config = await loop.run_in_executor(None, self.sheets.load_configuration)
            events = await loop.run_in_executor(None, self.sheets.load_schedule)
            patterns = await loop.run_in_executor(None, self.sheets.load_patterns)
            self._config = config
            self._events = {e.date: e for e in events}
            self._patterns = {p.pattern_id: p for p in patterns}
            self._last_sync = time.time()
            log.info("cache refreshed: %d events, %d patterns", len(events), len(patterns))

    def get_event(self, d: date) -> Optional[EventDate]:
        return self._events.get(d)

    def all_events(self) -> List[EventDate]:
        return list(self._events.values())

    def upsert_event(self, event: EventDate) -> None:
        self._events[event.date] = event

    def remove_event_assignment(self, d: date) -> None:
        existing = self._events.get(d)
        if existing:
            existing.host_discord_id = None
            existing.host_username = None
            existing.assigned_at = None
            existing.assigned_by = None
            existing.recurring_pattern_id = None

    def active_patterns_for(self, discord_id: str) -> List[RecurringPattern]:
        return [p for p in self._patterns.values() if p.is_active and p.host_discord_id == discord_id]

    def add_pattern(self, pattern: RecurringPattern) -> None:
        self._patterns[pattern.pattern_id] = pattern

    def deactivate_pattern(self, pattern_id: str) -> None:
        p = self._patterns.get(pattern_id)
        if p:
            p.is_active = False

    def invalidate(self) -> None:
        self._last_sync = 0.0
