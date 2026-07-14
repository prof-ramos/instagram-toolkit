"""
Serviço de ações em massa: follow/unfollow com rate limiting integrado.
"""

from __future__ import annotations

import logging

from instagrapi import Client
from instagrapi.exceptions import ClientError

from .cache import RelationsCache
from .config import UserNotFoundError
from .rate_limiter import RateLimiter
from .relations import RelationsService

logger = logging.getLogger(__name__)


class ActionsService:
    """
    Executa operações de follow/unfollow
    com rate limiting, invalidação de cache e coleta de resultados.
    """

    def __init__(
        self,
        client: Client,
        cache: RelationsCache,
        relations: RelationsService,
        rate_limiter: RateLimiter,
    ) -> None:
        self._client = client
        self.cache = cache
        self.relations = relations
        self.rate_limiter = rate_limiter

    def follow(self, user_id: int, *, invalidate: bool = True) -> bool:
        result = self._client.user_follow(user_id)
        if invalidate:
            self.cache.invalidate_relations()
        return result

    def unfollow(self, user_id: int, *, invalidate: bool = True) -> bool:
        result = self._client.user_unfollow(user_id)
        if invalidate:
            self.cache.invalidate_relations()
        return result

    def auto_follow_back(
        self, candidates: list[str], id_map: dict[str, int]
    ) -> tuple[int, list[str], list[str]]:
        success: list[str] = []
        failure: list[str] = []
        mutated = False
        try:
            for username in candidates:
                try:
                    user_id = id_map.get(username)
                    if user_id is None:
                        # Evita second-hop HTTP no caminho quente: só id_map
                        raise UserNotFoundError(
                            f"ID ausente no mapa para @{username}"
                        )
                    self.follow(user_id, invalidate=False)
                    mutated = True
                    success.append(username)
                    logger.info("✅ Seguindo de volta @%s", username)
                    self.rate_limiter.follow_delay()
                except (ClientError, UserNotFoundError, ValueError, OSError) as e:
                    logger.warning("❌ Falha ao seguir @%s: %s", username, e)
                    failure.append(f"{username} ({e})")
        finally:
            # Uma invalidação por lote, só se houve mutação real
            if mutated:
                self.cache.invalidate_relations()
        return len(success), success, failure

    def mass_unfollow(
        self, candidates: list[str], id_map: dict[str, int]
    ) -> tuple[int, list[str], list[str]]:
        success: list[str] = []
        failure: list[str] = []
        mutated = False
        try:
            for username in candidates:
                try:
                    user_id = id_map.get(username)
                    if user_id is None:
                        raise UserNotFoundError(
                            f"ID ausente no mapa para @{username}"
                        )
                    self.unfollow(user_id, invalidate=False)
                    mutated = True
                    success.append(username)
                    logger.info("✅ Deixou de seguir @%s", username)
                    self.rate_limiter.unfollow_delay()
                except (ClientError, UserNotFoundError, ValueError, OSError) as e:
                    logger.warning(
                        "❌ Falha ao deixar de seguir @%s: %s", username, e
                    )
                    failure.append(f"{username} ({e})")
        finally:
            if mutated:
                self.cache.invalidate_relations()
        return len(success), success, failure
