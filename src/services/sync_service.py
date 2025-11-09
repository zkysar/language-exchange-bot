"""Data synchronization service between Google Sheets and cache."""

import asyncio
import logging
from typing import Any, Callable, Optional

from src.services.cache_service import CacheService
from src.services.sheets_service import SheetsService


class SyncService:
    """
    Synchronize data between Google Sheets (authoritative) and local cache.

    Handles conflict resolution, change detection, and data consistency.
    """

    def __init__(
        self,
        sheets_service: SheetsService,
        cache_service: CacheService,
        ttl_seconds: int = 300,
    ):
        """
        Initialize sync service.

        Args:
            sheets_service: Google Sheets service instance
            cache_service: Cache service instance
            ttl_seconds: Cache TTL in seconds (default: 300 = 5 minutes)
        """
        self.sheets = sheets_service
        self.cache = cache_service
        self.ttl_seconds = ttl_seconds
        self.logger = logging.getLogger("discord_host_scheduler.sync")
        self._periodic_task: Optional[asyncio.Task] = None
        self._stop_periodic = False

    def sync_all(self, detect_conflicts: bool = False) -> dict[str, Any]:
        """
        Sync all data from Google Sheets to cache.

        Args:
            detect_conflicts: If True, detect and report conflicts

        Returns:
            Dictionary with sync stats (events_synced, patterns_synced, config_synced, conflicts)
        """
        stats = {
            "events_synced": 0,
            "patterns_synced": 0,
            "config_synced": 0,
            "conflicts": [],
        }

        try:
            # Detect changes if requested
            if detect_conflicts:
                changes = self.detect_changes()
                stats["conflicts"] = [
                    {"category": cat, "keys": keys} for cat, keys in changes.items() if keys
                ]

            # Sync configuration (Google Sheets is authoritative)
            stats["config_synced"] = self._sync_configuration()

            # Sync events (Google Sheets is authoritative)
            stats["events_synced"] = self._sync_events()

            # Sync recurring patterns (Google Sheets is authoritative)
            stats["patterns_synced"] = self._sync_recurring_patterns()

            # Update sync timestamp
            self.cache.update_sync_timestamp()

            self.logger.info(f"Sync completed: {stats}")
            return stats

        except Exception as e:
            self.logger.error(f"Sync failed: {e}")
            raise

    def _sync_configuration(self) -> int:
        """
        Sync configuration from Google Sheets to cache.

        Returns:
            Number of config entries synced
        """
        try:
            records = self.sheets.read_all_records(self.sheets.SHEET_CONFIGURATION)
            self.cache.increment_quota("reads", 1)

            config_data = {}
            for record in records:
                setting_key = record.get("setting_key")
                if setting_key:
                    config_data[setting_key] = {
                        "setting_value": record.get("setting_value"),
                        "setting_type": record.get("setting_type"),
                        "description": record.get("description"),
                        "updated_at": record.get("updated_at"),
                    }

            self.cache.set_many("configuration", config_data)
            self.logger.info(f"Synced {len(config_data)} configuration entries")
            return len(config_data)

        except Exception as e:
            self.logger.error(f"Failed to sync configuration: {e}")
            raise

    def _sync_events(self) -> int:
        """
        Sync event dates from Google Sheets to cache.

        Returns:
            Number of events synced
        """
        try:
            records = self.sheets.read_all_records(self.sheets.SHEET_SCHEDULE)
            self.cache.increment_quota("reads", 1)

            def _normalize_sheet_value(value: Any) -> Optional[str]:
                if value is None:
                    return None
                value_str = str(value).strip()
                return value_str or None

            events_data = {}
            for record in records:
                event_date = _normalize_sheet_value(record.get("date"))
                if event_date:
                    events_data[event_date] = {
                        "host_discord_id": _normalize_sheet_value(record.get("host_discord_id")),
                        "host_username": _normalize_sheet_value(record.get("host_username")),
                        "recurring_pattern_id": _normalize_sheet_value(
                            record.get("recurring_pattern_id")
                        ),
                        "assigned_at": _normalize_sheet_value(record.get("assigned_at")),
                        "assigned_by": _normalize_sheet_value(record.get("assigned_by")),
                        "notes": _normalize_sheet_value(record.get("notes")),
                    }

            self.cache.set_many("events", events_data)
            self.logger.info(f"Synced {len(events_data)} events")
            return len(events_data)

        except Exception as e:
            self.logger.error(f"Failed to sync events: {e}")
            raise

    def _sync_recurring_patterns(self) -> int:
        """
        Sync recurring patterns from Google Sheets to cache.

        Returns:
            Number of patterns synced
        """
        try:
            records = self.sheets.read_all_records(self.sheets.SHEET_RECURRING_PATTERNS)
            self.cache.increment_quota("reads", 1)

            patterns_data = {}
            for record in records:
                pattern_id = record.get("pattern_id")
                if pattern_id:
                    patterns_data[pattern_id] = {
                        "host_discord_id": record.get("host_discord_id"),
                        "host_username": record.get("host_username"),
                        "pattern_description": record.get("pattern_description"),
                        "pattern_rule": record.get("pattern_rule"),
                        "start_date": record.get("start_date"),
                        "end_date": record.get("end_date"),
                        "created_at": record.get("created_at"),
                        "is_active": record.get("is_active"),
                    }

            self.cache.set_many("recurring_patterns", patterns_data)
            self.logger.info(f"Synced {len(patterns_data)} recurring patterns")
            return len(patterns_data)

        except Exception as e:
            self.logger.error(f"Failed to sync recurring patterns: {e}")
            raise

    def detect_changes(self) -> dict[str, list[str]]:
        """
        Detect changes between Google Sheets and cache.

        Returns:
            Dictionary with lists of changed keys by category
        """
        changes = {"events": [], "recurring_patterns": [], "configuration": []}

        try:
            # Compare events
            sheets_events = self.sheets.read_all_records(self.sheets.SHEET_SCHEDULE)
            self.cache.increment_quota("reads", 1)
            cached_events = self.cache.get("events") or {}

            sheets_event_dict = {e.get("date"): e for e in sheets_events if e.get("date")}

            # Check for changes in events
            all_date_keys = set(sheets_event_dict.keys()) | set(cached_events.keys())
            for date_key in all_date_keys:
                sheets_data = sheets_event_dict.get(date_key)
                cached_data = cached_events.get(date_key)

                # Normalize data for comparison
                sheets_normalized = self._normalize_event_data(sheets_data) if sheets_data else None
                cached_normalized = self._normalize_event_data(cached_data) if cached_data else None

                if sheets_normalized != cached_normalized:
                    changes["events"].append(date_key)

            # Compare recurring patterns
            sheets_patterns = self.sheets.read_all_records(self.sheets.SHEET_RECURRING_PATTERNS)
            self.cache.increment_quota("reads", 1)
            cached_patterns = self.cache.get("recurring_patterns") or {}

            sheets_pattern_dict = {
                p.get("pattern_id"): p for p in sheets_patterns if p.get("pattern_id")
            }

            all_pattern_keys = set(sheets_pattern_dict.keys()) | set(cached_patterns.keys())
            for pattern_key in all_pattern_keys:
                sheets_data = sheets_pattern_dict.get(pattern_key)
                cached_data = cached_patterns.get(pattern_key)

                sheets_normalized = (
                    self._normalize_pattern_data(sheets_data) if sheets_data else None
                )
                cached_normalized = (
                    self._normalize_pattern_data(cached_data) if cached_data else None
                )

                if sheets_normalized != cached_normalized:
                    changes["recurring_patterns"].append(pattern_key)

            # Compare configuration
            sheets_config = self.sheets.read_all_records(self.sheets.SHEET_CONFIGURATION)
            self.cache.increment_quota("reads", 1)
            cached_config = self.cache.get("configuration") or {}

            sheets_config_dict = {
                c.get("setting_key"): c for c in sheets_config if c.get("setting_key")
            }

            all_config_keys = set(sheets_config_dict.keys()) | set(cached_config.keys())
            for config_key in all_config_keys:
                sheets_data = sheets_config_dict.get(config_key)
                cached_data = cached_config.get(config_key)

                sheets_normalized = (
                    self._normalize_config_data(sheets_data) if sheets_data else None
                )
                cached_normalized = (
                    self._normalize_config_data(cached_data) if cached_data else None
                )

                if sheets_normalized != cached_normalized:
                    changes["configuration"].append(config_key)

            self.logger.info(f"Detected changes: {changes}")
            return changes

        except Exception as e:
            self.logger.error(f"Failed to detect changes: {e}")
            raise

    def _normalize_event_data(self, data: dict) -> dict:
        """Normalize event data for comparison."""
        return {
            "host_discord_id": str(data.get("host_discord_id", "")),
            "host_username": str(data.get("host_username", "")),
            "recurring_pattern_id": str(data.get("recurring_pattern_id", "")),
            "assigned_at": str(data.get("assigned_at", "")),
            "assigned_by": str(data.get("assigned_by", "")),
            "notes": str(data.get("notes", "")),
        }

    def _normalize_pattern_data(self, data: dict) -> dict:
        """Normalize recurring pattern data for comparison."""
        return {
            "host_discord_id": str(data.get("host_discord_id", "")),
            "host_username": str(data.get("host_username", "")),
            "pattern_description": str(data.get("pattern_description", "")),
            "pattern_rule": str(data.get("pattern_rule", "")),
            "start_date": str(data.get("start_date", "")),
            "end_date": str(data.get("end_date", "")),
            "created_at": str(data.get("created_at", "")),
            "is_active": str(data.get("is_active", "")),
        }

    def _normalize_config_data(self, data: dict) -> dict:
        """Normalize configuration data for comparison."""
        if isinstance(data, dict) and "setting_value" in data:
            # Already in dict format from cache
            return {
                "setting_value": str(data.get("setting_value", "")),
                "setting_type": str(data.get("setting_type", "")),
                "description": str(data.get("description", "")),
                "updated_at": str(data.get("updated_at", "")),
            }
        else:
            # Raw data from sheets
            return {
                "setting_value": str(data.get("setting_value", "")),
                "setting_type": str(data.get("setting_type", "")),
                "description": str(data.get("description", "")),
                "updated_at": str(data.get("updated_at", "")),
            }

    def force_sync(self, detect_conflicts: bool = True) -> dict[str, Any]:
        """
        Force sync from Google Sheets (ignore cache).

        Args:
            detect_conflicts: If True, detect and report conflicts before syncing

        Returns:
            Sync stats dictionary with conflict information
        """
        self.logger.info("Forcing sync from Google Sheets")
        # Invalidate cache to force full sync
        self.cache.invalidate()
        return self.sync_all(detect_conflicts=detect_conflicts)

    async def start_periodic_sync(self, on_sync_complete: Optional[Callable] = None) -> None:
        """
        Start periodic sync task that runs every cache_ttl_seconds.

        Args:
            on_sync_complete: Optional callback function to call after each sync
        """
        if self._periodic_task and not self._periodic_task.done():
            self.logger.warning("Periodic sync task already running")
            return

        self._stop_periodic = False

        async def _periodic_sync_loop():
            """Periodic sync loop."""
            while not self._stop_periodic:
                try:
                    # Wait for TTL period
                    await asyncio.sleep(self.ttl_seconds)

                    if self._stop_periodic:
                        break

                    # Check if cache is stale
                    if self.cache.is_stale():
                        self.logger.info("Cache is stale, performing periodic sync")
                        try:
                            # Perform sync (use detect_conflicts=False for periodic sync)
                            stats = self.sync_all(detect_conflicts=False)
                            self.logger.info(f"Periodic sync completed: {stats}")

                            # Call callback if provided
                            if on_sync_complete:
                                try:
                                    if asyncio.iscoroutinefunction(on_sync_complete):
                                        await on_sync_complete(stats)
                                    else:
                                        on_sync_complete(stats)
                                except Exception as e:
                                    self.logger.error(f"Error in sync callback: {e}")

                        except Exception as e:
                            self.logger.error(f"Periodic sync failed: {e}", exc_info=True)
                    else:
                        self.logger.debug("Cache is still fresh, skipping sync")

                except asyncio.CancelledError:
                    self.logger.info("Periodic sync task cancelled")
                    break
                except Exception as e:
                    self.logger.error(f"Error in periodic sync loop: {e}", exc_info=True)
                    # Wait a bit before retrying to avoid tight error loops
                    await asyncio.sleep(60)

        self._periodic_task = asyncio.create_task(_periodic_sync_loop())
        self.logger.info(f"Started periodic sync task (interval: {self.ttl_seconds}s)")

    async def stop_periodic_sync(self) -> None:
        """Stop periodic sync task."""
        self._stop_periodic = True
        if self._periodic_task and not self._periodic_task.done():
            self._periodic_task.cancel()
            try:
                await self._periodic_task
            except asyncio.CancelledError:
                pass
            self.logger.info("Stopped periodic sync task")
