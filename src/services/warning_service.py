from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List

from src.models.models import Configuration
from src.services.cache_service import CacheService
from src.utils.date_parser import today_la
from src.utils.meeting_schedule import generate_meeting_dates


@dataclass
class WarningItem:
    event_date: date
    days_until: int
    severity: str  # "passive" or "urgent"


class WarningService:
    def __init__(self, cache: CacheService) -> None:
        self.cache = cache

    async def check(self, window_weeks: int = 4) -> List[WarningItem]:
        await self.cache.refresh()
        config: Configuration = self.cache.config
        today = today_la()
        horizon = today + timedelta(weeks=window_weeks)
        results: List[WarningItem] = []
        events_by_date = {e.date: e for e in self.cache.all_events()}
        meeting_dates = generate_meeting_dates(config, today, horizon)
        for i in range((horizon - today).days + 1):
            d = today + timedelta(days=i)
            if meeting_dates is not None and d not in meeting_dates:
                continue
            ev = events_by_date.get(d)
            if ev and ev.is_assigned:
                continue
            days_until = (d - today).days
            if days_until <= config.warning_urgent_days:
                severity = "urgent"
            elif days_until <= config.warning_passive_days:
                severity = "passive"
            else:
                continue
            results.append(WarningItem(event_date=d, days_until=days_until, severity=severity))
        return results
