import pytest

from cuysearch.cache import TTLCache


@pytest.mark.asyncio
async def test_ttl_cache_returns_and_clears_values() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=60)
    await cache.set("key", "value")

    assert await cache.get("key") == "value"
    await cache.clear()
    assert await cache.get("key") is None


@pytest.mark.asyncio
async def test_zero_ttl_disables_cache() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=0)
    await cache.set("key", "value")

    assert await cache.get("key") is None


@pytest.mark.asyncio
async def test_cache_evicts_oldest_entry_at_item_limit() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=60, max_entries=2, max_bytes=1_000)
    await cache.set("first", "1")
    await cache.set("second", "2")
    await cache.set("third", "3")

    assert await cache.get("first") is None
    assert await cache.get("second") == "2"
    assert await cache.get("third") == "3"


@pytest.mark.asyncio
async def test_cache_rejects_value_larger_than_byte_budget() -> None:
    cache: TTLCache[str] = TTLCache(ttl_seconds=60, max_entries=10, max_bytes=8)
    await cache.set("key", "a value that is too large")

    assert await cache.get("key") is None
