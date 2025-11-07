"""Unit tests for CacheService."""

import os
import tempfile
from pathlib import Path

import pytest

from src.services.cache_service import CacheService


@pytest.fixture
def temp_cache_file():
    """Create temporary cache file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        cache_path = f.name
    yield cache_path
    # Cleanup
    if os.path.exists(cache_path):
        os.remove(cache_path)


class TestCacheService:
    """Test CacheService."""

    def test_init_creates_empty_cache(self, temp_cache_file):
        """Test initializing cache creates empty structure."""
        cache = CacheService(cache_file=temp_cache_file, ttl_seconds=300)
        assert cache._cache_data is not None
        assert "events" in cache._cache_data
        assert "recurring_patterns" in cache._cache_data
        assert "configuration" in cache._cache_data

    def test_set_and_get_value(self, temp_cache_file):
        """Test setting and getting cache values."""
        cache = CacheService(cache_file=temp_cache_file, ttl_seconds=300)

        cache.set("events", "2025-11-11", {"host_discord_id": "123456789012345678"})
        result = cache.get("events", "2025-11-11")

        assert result == {"host_discord_id": "123456789012345678"}

    def test_set_many_values(self, temp_cache_file):
        """Test setting multiple values at once."""
        cache = CacheService(cache_file=temp_cache_file, ttl_seconds=300)

        data = {
            "2025-11-11": {"host_discord_id": "123456789012345678"},
            "2025-11-12": {"host_discord_id": "987654321098765432"},
        }
        cache.set_many("events", data)

        result = cache.get("events")
        assert len(result) == 2
        assert "2025-11-11" in result

    def test_delete_value(self, temp_cache_file):
        """Test deleting cache value."""
        cache = CacheService(cache_file=temp_cache_file, ttl_seconds=300)

        cache.set("events", "2025-11-11", {"host_discord_id": "123456789012345678"})
        cache.delete("events", "2025-11-11")

        result = cache.get("events", "2025-11-11")
        assert result is None

    def test_invalidate_cache(self, temp_cache_file):
        """Test invalidating cache."""
        cache = CacheService(cache_file=temp_cache_file, ttl_seconds=300)

        cache.update_sync_timestamp()
        assert not cache.is_stale()

        cache.invalidate()
        assert cache.is_stale()

    def test_quota_tracking(self, temp_cache_file):
        """Test quota usage tracking."""
        cache = CacheService(cache_file=temp_cache_file, ttl_seconds=300)

        cache.increment_quota("reads", 5)
        cache.increment_quota("writes", 2)

        quota = cache.get_quota_usage()
        assert quota["reads"] == 5
        assert quota["writes"] == 2

    def test_clear_cache(self, temp_cache_file):
        """Test clearing cache."""
        cache = CacheService(cache_file=temp_cache_file, ttl_seconds=300)

        cache.set("events", "2025-11-11", {"host_discord_id": "123456789012345678"})
        cache.clear()

        assert not Path(temp_cache_file).exists()
