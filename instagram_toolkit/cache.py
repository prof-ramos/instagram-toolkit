"""
Cache em memória com TTL para dados de followers/following.
"""

import time
from dataclasses import dataclass
from typing import Any

from .config import DEFAULT_TTL


@dataclass
class _CacheEntry:
    data: Any
    timestamp: float


class RelationsCache:
    """
    Cache em memória para followers/following com TTL configurável.
    Invalida automaticamente após operações de follow/unfollow.
    """

    def __init__(self, ttl: float = DEFAULT_TTL, enabled: bool = True) -> None:
        self.ttl = ttl
        self.enabled = enabled
        self._store: dict[str, _CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        if not self.enabled:
            return None
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() - entry.timestamp > self.ttl:
            del self._store[key]
            return None
        return entry.data

    def set(self, key: str, data: Any) -> None:
        if not self.enabled:
            return
        self._store[key] = _CacheEntry(data=data, timestamp=time.monotonic())

    def invalidate(self, *keys: str) -> None:
        for key in keys:
            self._store.pop(key, None)

    def invalidate_relations(self) -> None:
        """Invalida cache de followers e following (chamado após follow/unfollow)."""
        self.invalidate("followers", "following")

    def status(self) -> str:
        if not self.enabled:
            return "🛈 Cache desabilitado (--no-cache)"
        now = time.monotonic()
        entries = [
            f"{k}: {max(0, int(self.ttl - (now - e.timestamp)))}s"
            for k, e in self._store.items()
        ]
        if not entries:
            return "📦 Cache vazio"
        return "📊 Cache: " + " | ".join(entries)
