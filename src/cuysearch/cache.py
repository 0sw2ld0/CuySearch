import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass(slots=True)
class _CacheEntry(Generic[T]):
    value: T
    expires_at: float
    size_bytes: int


class TTLCache(Generic[T]):
    """Caché simple, acotada al proceso.

    El candado es de hilos y nunca se espera dentro de él, así que la caché
    sirve igual desde tareas asyncio de distintos bucles.
    """

    def __init__(
        self,
        ttl_seconds: int,
        max_entries: int = 128,
        max_bytes: int = 4_000_000,
    ) -> None:
        self._ttl_seconds = max(0, ttl_seconds)
        self._max_entries = max(0, max_entries)
        self._max_bytes = max(0, max_bytes)
        self._entries: OrderedDict[str, _CacheEntry[T]] = OrderedDict()
        self._size_bytes = 0
        self._lock = threading.Lock()

    @staticmethod
    def _value_size(value: T) -> int:
        serializer = getattr(value, "model_dump_json", None)
        if callable(serializer):
            return len(serializer().encode("utf-8"))
        if isinstance(value, bytes):
            return len(value)
        if isinstance(value, str):
            return len(value.encode("utf-8"))
        return len(repr(value).encode("utf-8"))

    def _remove(self, key: str) -> None:
        entry = self._entries.pop(key, None)
        if entry is not None:
            self._size_bytes -= entry.size_bytes

    def _prune_expired(self, now: float) -> None:
        for key, entry in list(self._entries.items()):
            if entry.expires_at <= now:
                self._remove(key)

    async def get(self, key: str) -> T | None:
        if self._ttl_seconds == 0:
            return None
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= time.monotonic():
                self._remove(key)
                return None
            self._entries.move_to_end(key)
            return entry.value

    async def set(self, key: str, value: T) -> None:
        if self._ttl_seconds == 0 or self._max_entries == 0 or self._max_bytes == 0:
            return
        value_size = self._value_size(value)
        entry_size = len(key.encode("utf-8")) + value_size
        if entry_size > self._max_bytes:
            return
        with self._lock:
            self._prune_expired(time.monotonic())
            self._remove(key)
            self._entries[key] = _CacheEntry(
                value=value,
                expires_at=time.monotonic() + self._ttl_seconds,
                size_bytes=entry_size,
            )
            self._size_bytes += entry_size
            while len(self._entries) > self._max_entries or self._size_bytes > self._max_bytes:
                oldest_key = next(iter(self._entries))
                self._remove(oldest_key)

    async def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._size_bytes = 0
