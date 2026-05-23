"""
Serviço de ações em massa: follow/unfollow com rate limiting integrado.
"""

import logging

from instagrapi import Client

from .cache import RelationsCache
from .config import UserNotFoundError
from .rate_limiter import RateLimiter
from .relations import RelationsService

logger = logging.getLogger(__name__)


class ActionsService:
    """
    Responsabilidade única: executar operações de follow/unfollow
    com rate limiting, invalidação de cache e coleta de resultados.
    """

    def __init__(
        self,
        client: Client,
        cache: RelationsCache,
        relations: RelationsService,
        rate_limiter: RateLimiter,
    ) -> None:
        self.cl = client
        self.cache = cache
        self.relations = relations
        self.rate_limiter = rate_limiter

    def follow(self, user_id: int) -> bool:
        result = self.cl.user_follow(user_id)
        self.cache.invalidate_relations()
        return result

    def unfollow(self, user_id: int) -> bool:
        result = self.cl.user_unfollow(user_id)
        self.cache.invalidate_relations()
        return result

    def auto_follow_back(
        self, usernames: list[str], id_map: dict[str, int]
    ) -> tuple[int, list[str], list[str]]:
        success: list[str] = []
        failure: list[str] = []
        for username in usernames:
            try:
                user_id = id_map.get(username) or self.relations.resolve_user_id(username)
                if user_id is None:
                    raise UserNotFoundError(f"Usuário @{username} não encontrado")
                self.follow(user_id)
                success.append(username)
                logger.info("✅ Seguindo de volta @%s", username)
                self.rate_limiter.follow_delay()
            except Exception as e:
                logger.warning("❌ Falha ao seguir @%s: %s", username, e)
                failure.append(f"{username} ({e})")
        return len(success), success, failure

    def mass_unfollow(
        self, usernames: list[str], id_map: dict[str, int]
    ) -> tuple[int, list[str], list[str]]:
        success: list[str] = []
        failure: list[str] = []
        for username in usernames:
            try:
                user_id = id_map.get(username) or self.relations.resolve_user_id(username)
                if user_id is None:
                    raise UserNotFoundError(f"Usuário @{username} não encontrado")
                self.unfollow(user_id)
                success.append(username)
                logger.info("✅ Deixou de seguir @%s", username)
                self.rate_limiter.unfollow_delay()
            except Exception as e:
                logger.warning("❌ Falha ao deixar de seguir @%s: %s", username, e)
                failure.append(f"{username} ({e})")
        return len(success), success, failure
