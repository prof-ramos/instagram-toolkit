"""
Serviço de rastreamento de seguidores ao longo do tempo.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from instagrapi import Client
from instagrapi.exceptions import ClientError

from .cache import RelationMap, RelationsCache
from .models import TrackerResult
from .rate_limiter import RateLimiter
from .relations import to_relation_map
from .storage import HistoryStorage

logger = logging.getLogger(__name__)


class TrackerService:
    """
    Detecta ganhos e perdas de seguidores comparando snapshots do histórico.
    Reutiliza RelationsCache quando há snapshot complete fresco do mesmo user.
    """

    def __init__(
        self,
        client: Client,
        storage: HistoryStorage,
        rate_limiter: RateLimiter,
        cache: RelationsCache | None = None,
    ) -> None:
        self._client = client
        self.storage = storage
        self._rate_limiter = rate_limiter
        self.cache = cache

    def get_all_followers_safe(
        self, user_id: int, max_retries: int = 3
    ) -> RelationMap:
        """Fetch completo sem limite (para tracker), com retry, backoff e cache."""
        # Cache keys always represent the authenticated account — never reuse
        # for a different user_id.
        cache_eligible = (
            self.cache is not None and user_id == self._client.user_id
        )
        if cache_eligible:
            cached = self.cache.get("followers", require_complete=True)
            if cached is not None:
                logger.info(
                    "📦 Tracker usando cache complete de followers (%d).",
                    len(cached),
                )
                return cached

        last_exc: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    "📥 Carregando todos os seguidores (tentativa %d/%d)...",
                    attempt,
                    max_retries,
                )
                raw = self._client.user_followers(user_id, amount=0)
                mapped = to_relation_map(raw)
                logger.info("✅ %d seguidores carregados.", len(mapped))
                if cache_eligible:
                    self.cache.set(
                        "followers",
                        mapped,
                        complete=True,
                        fetch_amount=0,
                    )
                return mapped
            except ClientError as e:
                last_exc = e
                if "rate" in str(e).lower():
                    self._rate_limiter.backoff(attempt)
                else:
                    raise
            except Exception as e:
                last_exc = e
                if attempt == max_retries:
                    raise
                logger.warning("⚠️ Erro: %s. Tentando novamente...", e)
                time.sleep(8)
        raise RuntimeError(
            f"Falha ao carregar seguidores após {max_retries} tentativas."
        ) from last_exc

    def run(self) -> TrackerResult:
        """Executa um ciclo de rastreamento e retorna o resultado."""
        current = self.get_all_followers_safe(self._client.user_id)
        current_data = {str(pk): u.username for pk, u in current.items()}
        history = self.storage.load()

        if history is None:
            backup = self.storage.save(current_data)
            if backup is None:
                raise RuntimeError("Falha ao salvar histórico inicial.")
            return TrackerResult(
                is_first_run=True,
                backup_path=backup,
                unfollowed=set(),
                new_followers=set(),
                history={},
                current_data={},
            )

        old_ids = set(history.keys())
        new_ids = set(current_data.keys())
        backup = self.storage.save(current_data)
        if backup is None:
            raise RuntimeError("Falha ao salvar histórico atualizado.")
        return TrackerResult(
            is_first_run=False,
            backup_path=backup,
            unfollowed=old_ids - new_ids,
            new_followers=new_ids - old_ids,
            history=history,
            current_data=current_data,
        )
