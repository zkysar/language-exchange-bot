"""Cache service for JSON file-based caching."""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional


class CacheService:
    """
    JSON file-based cache service for offline resilience.

    Provides TTL-based caching, cache invalidation, and quota tracking.
    """

    def __init__(self, cache_file: str = "cache.json", ttl_seconds: int = 300):
        """
        Initialize cache service.

        Args:
            cache_file: Path to cache file (default: cache.json)
            ttl_seconds: Cache TTL in seconds (default: 300 = 5 minutes)
        """
        self.cache_file = Path(cache_file)
        self.ttl_seconds = ttl_seconds
        self.logger = logging.getLogger("discord_host_scheduler.cache")
        self._cache_data: Optional[dict] = None
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cache from file."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r") as f:
                    self._cache_data = json.load(f)
                self.logger.info(f"Cache loaded from {self.cache_file}")
            except (json.JSONDecodeError, IOError) as e:
                self.logger.error(f"Failed to load cache: {e}")
                self._cache_data = self._get_empty_cache()
        else:
            self.logger.info("No cache file found, starting with empty cache")
            self._cache_data = self._get_empty_cache()

    def _get_empty_cache(self) -> dict:
        """Get empty cache structure."""
        return {
            "last_sync": None,
            "events": {},
            "recurring_patterns": {},
            "configuration": {},
            "quota_usage": {"reads": 0, "writes": 0, "last_reset": datetime.now().isoformat()},
            "cache_version": "1.0",
        }

    def _save_cache(self) -> None:
        """Save cache to file."""
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self._cache_data, f, indent=2)
            self.logger.info(f"Cache saved to {self.cache_file}")
        except IOError as e:
            self.logger.error(f"Failed to save cache: {e}")

    def is_stale(self) -> bool:
        """
        Check if cache is stale (expired based on TTL).

        Returns:
            True if cache is stale, False otherwise
        """
        if not self._cache_data or not self._cache_data.get("last_sync"):
            return True

        last_sync = datetime.fromisoformat(self._cache_data["last_sync"])
        age = datetime.now() - last_sync
        return age.total_seconds() > self.ttl_seconds

    def get_age_seconds(self) -> Optional[float]:
        """
        Get cache age in seconds.

        Returns:
            Cache age in seconds, or None if no last_sync timestamp
        """
        if not self._cache_data or not self._cache_data.get("last_sync"):
            return None

        last_sync = datetime.fromisoformat(self._cache_data["last_sync"])
        age = datetime.now() - last_sync
        return age.total_seconds()

    def get(self, category: str, key: str = None) -> Any:
        """
        Get value from cache.

        Args:
            category: Cache category (events, recurring_patterns, configuration)
            key: Optional key within category (returns entire category if None)

        Returns:
            Cached value, or None if not found
        """
        if not self._cache_data:
            return None

        category_data = self._cache_data.get(category, {})

        if key is None:
            return category_data

        return category_data.get(key)

    def set(self, category: str, key: str, value: Any) -> None:
        """
        Set value in cache.

        Args:
            category: Cache category (events, recurring_patterns, configuration)
            key: Key within category
            value: Value to cache
        """
        if not self._cache_data:
            self._cache_data = self._get_empty_cache()

        if category not in self._cache_data:
            self._cache_data[category] = {}

        self._cache_data[category][key] = value
        self._save_cache()

    def set_many(self, category: str, data: dict) -> None:
        """
        Set multiple values in cache category.

        Args:
            category: Cache category (events, recurring_patterns, configuration)
            data: Dictionary of key-value pairs to cache
        """
        if not self._cache_data:
            self._cache_data = self._get_empty_cache()

        self._cache_data[category] = data
        self._save_cache()

    def delete(self, category: str, key: str = None) -> None:
        """
        Delete value from cache.

        Args:
            category: Cache category (events, recurring_patterns, configuration)
            key: Key to delete (deletes entire category if None)
        """
        if not self._cache_data:
            return

        if key is None:
            # Delete entire category
            if category in self._cache_data:
                del self._cache_data[category]
        else:
            # Delete specific key
            if category in self._cache_data and key in self._cache_data[category]:
                del self._cache_data[category][key]

        self._save_cache()

    def invalidate(self) -> None:
        """Invalidate entire cache (mark as stale)."""
        if self._cache_data:
            self._cache_data["last_sync"] = None
            self._save_cache()
        self.logger.info("Cache invalidated")

    def update_sync_timestamp(self) -> None:
        """Update last_sync timestamp to current time."""
        if not self._cache_data:
            self._cache_data = self._get_empty_cache()

        self._cache_data["last_sync"] = datetime.now().isoformat()
        self._save_cache()
        self.logger.info("Cache sync timestamp updated")

    def increment_quota(self, operation: str, count: int = 1) -> None:
        """
        Increment quota usage counter.

        Args:
            operation: Operation type (reads, writes)
            count: Number of operations to increment (default 1)
        """
        if not self._cache_data:
            self._cache_data = self._get_empty_cache()

        quota = self._cache_data.get("quota_usage", {})
        quota[operation] = quota.get(operation, 0) + count
        self._cache_data["quota_usage"] = quota
        self._save_cache()

    def get_quota_usage(self) -> dict:
        """
        Get current quota usage.

        Returns:
            Dictionary with quota usage stats
        """
        if not self._cache_data:
            return {"reads": 0, "writes": 0, "last_reset": None}

        return self._cache_data.get("quota_usage", {"reads": 0, "writes": 0, "last_reset": None})

    def reset_quota(self) -> None:
        """Reset quota usage counters."""
        if not self._cache_data:
            self._cache_data = self._get_empty_cache()

        self._cache_data["quota_usage"] = {
            "reads": 0,
            "writes": 0,
            "last_reset": datetime.now().isoformat(),
        }
        self._save_cache()
        self.logger.info("Quota usage reset")

    def clear(self) -> None:
        """Clear entire cache (delete cache file)."""
        if self.cache_file.exists():
            os.remove(self.cache_file)
            self.logger.info(f"Cache file deleted: {self.cache_file}")

        self._cache_data = self._get_empty_cache()
