"""
Cache em memória com TTL para followers/following.

Distingue entradas *complete* (análise/export/tracker) de *preview*
(listagens limitadas), evitando envenenar análises com snapshots truncados.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from .config import DEFAULT_TTL
from .models import UserRecord

logger = logging.getLogger(__name__)

RelationMap = dict[int, UserRecord]


@dataclass
class _CacheEntry:
    data: RelationMap
    timestamp: float
    complete: bool
    fetch_amount: int  # 0 = unlimited / full fetch requested


class RelationsCache:
    """
    Cache em memória para followers/following com TTL configurável.
    Thread-safe (RLock). Complete snapshots are sticky until TTL/invalidate.
    """

    def __init__(self, ttl: float = DEFAULT_TTL, enabled: bool = True) -> None:
        self.ttl = ttl
        self.enabled = enabled
        self._store: dict[str, _CacheEntry] = {}
        self._lock = threading.RLock()

    def get(
        self,
        key: str,
        *,
        require_complete: bool = False,
    ) -> RelationMap | None:
        if not self.enabled:
            return None
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.monotonic() - entry.timestamp > self.ttl:
                del self._store[key]
                return None
            if require_complete and not entry.complete:
                return None
            return entry.data

    def set(
        self,
        key: str,
        data: RelationMap,
        *,
        complete: bool = True,
        fetch_amount: int = 0,
    ) -> None:
        if not self.enabled:
            return
        with self._lock:
            existing = self._get_fresh_entry(key)
            # Never demote a still-fresh complete snapshot to partial
            if existing is not None and existing.complete and not complete:
                logger.debug(
                    "Ignorando set partial de %s: entrada complete ainda válida.",
                    key,
                )
                return
            self._store[key] = _CacheEntry(
                data=data,
                timestamp=time.monotonic(),
                complete=complete,
                fetch_amount=fetch_amount,
            )

    def is_complete(self, key: str) -> bool:
        if not self.enabled:
            return False
        with self._lock:
            entry = self._get_fresh_entry(key)
            return bool(entry and entry.complete)

    def invalidate(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                self._store.pop(key, None)

    def invalidate_relations(self) -> None:
        """Invalida cache de followers e following (após follow/unfollow)."""
        self.invalidate("followers", "following")

    def status(self) -> str:
        if not self.enabled:
            return "🛈 Cache desabilitado (--no-cache)"
        with self._lock:
            now = time.monotonic()
            parts: list[str] = []
            for key, entry in self._store.items():
                remaining = max(0, int(self.ttl - (now - entry.timestamp)))
                flag = "full" if entry.complete else "partial"
                parts.append(f"{key}:{len(entry.data)}({flag}) {remaining}s")
            if not parts:
                return "📦 Cache vazio"
            return "📊 Cache: " + " | ".join(parts)

    def _get_fresh_entry(self, key: str) -> _CacheEntry | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() - entry.timestamp > self.ttl:
            del self._store[key]
            return None
        return entry
