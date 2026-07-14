"""
Serviço de relações: followers, following, mutuals e consultas derivadas.
"""

import logging
from pathlib import Path
from typing import Any

from instagrapi import Client
from instagrapi.exceptions import ClientError

from .cache import RelationsCache
from .config import FETCH_LIMIT
from .models import FollowerData, UserRecord
from .storage import HistoryStorage

logger = logging.getLogger(__name__)


class RelationsService:
    """
    Busca, compara e exporta
    listas de seguidores e seguidos.
    """

    def __init__(self, client: Client, cache: RelationsCache, storage: HistoryStorage) -> None:
        self._client = client
        self.cache = cache
        self.storage = storage

    def get_my_followers(self, limit: int = FETCH_LIMIT) -> dict[int, Any]:
        cached = self.cache.get("followers")
        if cached is not None:
            logger.debug("[cache hit] followers (%d entradas)", len(cached))
            return cached
        logger.info("📥 Buscando seguidores (limite: %d)...", limit)
        data = self._client.user_followers(self._client.user_id, amount=limit)
        if len(data) >= limit:
            logger.warning(
                "⚠️ Resultado truncado: %d/%d. Aumente FETCH_LIMIT ou use --no-cache.",
                len(data), limit,
            )
        self.cache.set("followers", data)
        return data

    def get_my_following(self, limit: int = FETCH_LIMIT) -> dict[int, Any]:
        cached = self.cache.get("following")
        if cached is not None:
            logger.debug("[cache hit] following (%d entradas)", len(cached))
            return cached
        logger.info("📥 Buscando seguidos (limite: %d)...", limit)
        data = self._client.user_following(self._client.user_id, amount=limit)
        if len(data) >= limit:
            logger.warning(
                "⚠️ Resultado truncado: %d/%d. Aumente FETCH_LIMIT ou use --no-cache.",
                len(data), limit,
            )
        self.cache.set("following", data)
        return data

    def get_relations_parallel(self) -> tuple[dict[int, Any], dict[int, Any]]:
        """Busca followers e following, priorizando cache."""
        cached_followers = self.cache.get("followers")
        cached_following = self.cache.get("following")

        if cached_followers is not None and cached_following is not None:
            logger.debug("[cache hit] relations completas (sem chamada de rede)")
            return cached_followers, cached_following

        user_id = self._client.user_id
        if cached_followers is None:
            cached_followers = self._client.user_followers(user_id, amount=FETCH_LIMIT)
            self.cache.set("followers", cached_followers)
        if cached_following is None:
            cached_following = self._client.user_following(user_id, amount=FETCH_LIMIT)
            self.cache.set("following", cached_following)

        return cached_followers, cached_following

    def get_followers(self, target_id: int | None = None, limit: int = 50) -> dict[int, Any]:
        """Return followers for a user.

        When *target_id* is provided the cache is bypassed and the API is
        queried directly for that user.  Otherwise the authenticated user's
        followers are returned, served from cache when available.
        """
        if target_id is None:
            return self.get_my_followers(limit=limit)
        return self._client.user_followers(target_id, amount=limit)

    def get_following(self, target_id: int | None = None, limit: int = 50) -> dict[int, Any]:
        """Return following for a user.

        When *target_id* is provided the cache is bypassed and the API is
        queried directly for that user.  Otherwise the authenticated user's
        following are returned, served from cache when available.
        """
        if target_id is None:
            return self.get_my_following(limit=limit)
        return self._client.user_following(target_id, amount=limit)

    def get_non_followers_back(self) -> list[str]:
        followers, following = self.get_relations_parallel()
        return sorted(
            {u.username for u in following.values()}
            - {u.username for u in followers.values()}
        )

    def get_mutuals(self) -> list[str]:
        followers, following = self.get_relations_parallel()
        return sorted(
            {u.username for u in following.values()}
            & {u.username for u in followers.values()}
        )

    def get_auto_follow_back_candidates(self) -> tuple[list[str], dict[str, int]]:
        followers, following = self.get_relations_parallel()
        followers_map = {u.username: pk for pk, u in followers.items()}
        following_set = {u.username for u in following.values()}
        candidates = sorted(followers_map.keys() - following_set)
        return candidates, {u: followers_map[u] for u in candidates}

    def get_mass_unfollow_candidates(self) -> tuple[list[str], dict[str, int]]:
        followers, following = self.get_relations_parallel()
        followers_set = {u.username for u in followers.values()}
        following_map = {u.username: pk for pk, u in following.items()}
        candidates = sorted(following_map.keys() - followers_set)
        return candidates, {u: following_map[u] for u in candidates}

    def export_followers(self, filename: Path) -> int:
        followers = self.get_my_followers()
        data: list[FollowerData] = [
            {
                "id": str(pk),
                "username": u.username,
                "full_name": u.full_name,
                "is_private": u.is_private,
                "is_verified": u.is_verified,
                "follower_count": getattr(u, "follower_count", 0),
                "following_count": getattr(u, "following_count", 0),
                "media_count": getattr(u, "media_count", 0),
                "biography": getattr(u, "biography", ""),
                "external_url": getattr(u, "external_url", None),
            }
            for pk, u in followers.items()
        ]
        self.storage.secure_write_json(filename, data)
        return len(data)

    def export_following(self, filename: Path) -> int:
        following = self.get_my_following()
        data: list[FollowerData] = [
            {
                "id": str(pk),
                "username": u.username,
                "full_name": u.full_name,
                "is_private": u.is_private,
                "is_verified": u.is_verified,
                "follower_count": getattr(u, "follower_count", 0),
                "following_count": getattr(u, "following_count", 0),
                "media_count": getattr(u, "media_count", 0),
                "biography": getattr(u, "biography", ""),
                "external_url": getattr(u, "external_url", None),
            }
            for pk, u in following.items()
        ]
        self.storage.secure_write_json(filename, data)
        return len(data)

    def get_user_info(self, user_id: int) -> UserRecord:
        """Wrap raw instagrapi user_info into the internal UserRecord model."""
        raw = self._client.user_info(user_id)
        return UserRecord.from_instagrapi(raw.pk, raw)

    def get_user_medias(self, user_id: int, count: int) -> list[Any]:
        """Return up to *count* recent medias for the given user."""
        return self._client.user_medias(user_id, amount=count)

    def resolve_user_id(self, identifier: str | int) -> int | None:
        identifier_str = str(identifier).strip().lstrip("@")
        if not identifier_str:
            logger.error("Identificador de usuário vazio.")
            return None
        if identifier_str.isdigit():
            return int(identifier_str)
        try:
            return int(self._client.user_id_from_username(identifier_str))
        except (ClientError, OSError) as e:
            logger.error("Não foi possível resolver @%s: %s", identifier_str, e)
            return None
