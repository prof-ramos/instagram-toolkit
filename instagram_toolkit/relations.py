"""
Serviço de relações: followers, following, mutuals e consultas derivadas.
"""

from __future__ import annotations

import logging
from itertools import islice
from pathlib import Path
from typing import Any

from instagrapi import Client
from instagrapi.exceptions import ClientError

from .cache import RelationMap, RelationsCache
from .config import resolve_fetch_limit
from .models import FollowerData, UserRecord
from .storage import HistoryStorage

logger = logging.getLogger(__name__)


def to_relation_map(raw: dict[Any, Any]) -> RelationMap:
    """Converte payload instagrapi (ou UserRecord) em mapa enxuto."""
    result: RelationMap = {}
    for pk, user in raw.items():
        pk_int = int(pk)
        if isinstance(user, UserRecord):
            result[pk_int] = user
        else:
            result[pk_int] = UserRecord.from_instagrapi(pk_int, user)
    return result


# Alias interno legado
_to_relation_map = to_relation_map


def _is_complete(fetch_amount: int, size: int) -> bool:
    """amount=0 é full; amount>0 só é complete se não bateu no teto."""
    if fetch_amount == 0:
        return True
    return size < fetch_amount


class RelationsService:
    """
    Busca, compara e exporta listas de seguidores e seguidos.
    """

    def __init__(
        self,
        client: Client,
        cache: RelationsCache,
        storage: HistoryStorage,
        fetch_limit: int | None = None,
    ) -> None:
        self._client = client
        self.cache = cache
        self.storage = storage
        self.fetch_limit = resolve_fetch_limit() if fetch_limit is None else fetch_limit

    # ------------------------------------------------------------------
    # Fetch + cache
    # ------------------------------------------------------------------

    def get_my_followers(self, *, complete: bool = True) -> RelationMap:
        """Lista completa (ou melhor snapshot complete em cache) dos meus followers."""
        if complete:
            cached = self.cache.get("followers", require_complete=True)
            if cached is not None:
                logger.debug("[cache hit] followers complete (%d)", len(cached))
                return cached
            return self._fetch_and_store(
                "followers", self._client.user_id, require_complete=True
            )

        return self._preview("followers", limit=50)

    def get_my_following(self, *, complete: bool = True) -> RelationMap:
        if complete:
            cached = self.cache.get("following", require_complete=True)
            if cached is not None:
                logger.debug("[cache hit] following complete (%d)", len(cached))
                return cached
            return self._fetch_and_store(
                "following", self._client.user_id, require_complete=True
            )

        return self._preview("following", limit=50)

    def list_followers(self, limit: int = 50) -> tuple[RelationMap, int]:
        """
        Preview para o menu: fatia de cache complete se existir;
        caso contrário fetch limitado que NÃO grava como complete.
        Retorna (página, total_conhecido).
        """
        return self._list_page("followers", limit)

    def list_following(self, limit: int = 50) -> tuple[RelationMap, int]:
        return self._list_page("following", limit)

    def get_relations(self) -> tuple[RelationMap, RelationMap]:
        """
        Obtém followers e following completos.

        Fetches are sequential on a shared instagrapi.Client (requests.Session
        is not thread-safe).
        """
        followers = self.cache.get("followers", require_complete=True)
        following = self.cache.get("following", require_complete=True)

        if followers is not None and following is not None:
            logger.debug("[cache hit] relations completas (sem rede)")
            return followers, following

        user_id = self._client.user_id
        if followers is None:
            followers = self._fetch_and_store(
                "followers", user_id, require_complete=True
            )
        if following is None:
            following = self._fetch_and_store(
                "following", user_id, require_complete=True
            )

        if followers is None or following is None:
            raise RuntimeError("Falha ao carregar relações completas.")
        return followers, following

    # Alias legado
    def get_relations_parallel(self) -> tuple[RelationMap, RelationMap]:
        return self.get_relations()

    def get_followers(
        self,
        target_id: int | None = None,
        limit: int = 50,
        *,
        preview: bool = False,
    ) -> RelationMap:
        if target_id is not None:
            raw = self._client.user_followers(target_id, amount=limit)
            return to_relation_map(raw)
        if preview:
            page, _total = self.list_followers(limit=limit)
            return page
        return self.get_my_followers(complete=True)

    def get_following(
        self,
        target_id: int | None = None,
        limit: int = 50,
        *,
        preview: bool = False,
    ) -> RelationMap:
        if target_id is not None:
            raw = self._client.user_following(target_id, amount=limit)
            return to_relation_map(raw)
        if preview:
            page, _total = self.list_following(limit=limit)
            return page
        return self.get_my_following(complete=True)

    # ------------------------------------------------------------------
    # Derived queries
    # ------------------------------------------------------------------

    def get_non_followers_back(self) -> list[str]:
        followers, following = self.get_relations()
        return sorted(
            {u.username for u in following.values()}
            - {u.username for u in followers.values()}
        )

    def get_mutuals(self) -> list[str]:
        followers, following = self.get_relations()
        return sorted(
            {u.username for u in following.values()}
            & {u.username for u in followers.values()}
        )

    def get_auto_follow_back_candidates(self) -> tuple[list[str], dict[str, int]]:
        followers, following = self.get_relations()
        followers_map = {u.username: pk for pk, u in followers.items()}
        following_set = {u.username for u in following.values()}
        candidates = sorted(followers_map.keys() - following_set)
        return candidates, {u: followers_map[u] for u in candidates}

    def get_mass_unfollow_candidates(self) -> tuple[list[str], dict[str, int]]:
        followers, following = self.get_relations()
        followers_set = {u.username for u in followers.values()}
        following_map = {u.username: pk for pk, u in following.items()}
        candidates = sorted(following_map.keys() - followers_set)
        return candidates, {u: following_map[u] for u in candidates}

    def export_followers(self, filename: Path) -> int:
        followers = self.get_my_followers(complete=True)
        data = self._export_rows(followers)
        self.storage.secure_write_json(filename, data, pretty=True)
        return len(data)

    def export_following(self, filename: Path) -> int:
        following = self.get_my_following(complete=True)
        data = self._export_rows(following)
        self.storage.secure_write_json(filename, data, pretty=True)
        return len(data)

    def get_user_info(self, user_id: int) -> UserRecord:
        raw = self._client.user_info(user_id)
        return UserRecord.from_instagrapi(raw.pk, raw)

    def get_user_medias(self, user_id: int, count: int) -> list[Any]:
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

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _list_page(self, key: str, limit: int) -> tuple[RelationMap, int]:
        limit = max(1, limit)
        complete = self.cache.get(key, require_complete=True)
        if complete is not None:
            page = dict(islice(complete.items(), limit))
            return page, len(complete)

        partial = self.cache.get(key, require_complete=False)
        if partial is not None and len(partial) >= limit:
            page = dict(islice(partial.items(), limit))
            return page, len(partial)

        raw_amount = limit
        logger.info("📥 Preview %s (limit=%d, sem marcar complete)...", key, limit)
        if key == "followers":
            raw = self._client.user_followers(self._client.user_id, amount=raw_amount)
        else:
            raw = self._client.user_following(self._client.user_id, amount=raw_amount)
        mapped = to_relation_map(raw)
        self.cache.set(key, mapped, complete=False, fetch_amount=raw_amount)
        return mapped, len(mapped)

    def _preview(self, key: str, limit: int) -> RelationMap:
        page, _ = self._list_page(key, limit)
        return page

    def _fetch_and_store(
        self,
        key: str,
        user_id: int,
        *,
        require_complete: bool = True,
    ) -> RelationMap:
        """
        Fetch and cache. When require_complete=True and FETCH_LIMIT truncates,
        automatically re-fetch with amount=0 so analyses never see partial data.
        """
        raw, amount = self._raw_fetch(key, user_id, amount=self.fetch_limit)
        mapped = self._store_raw(key, raw, amount)

        if require_complete and not _is_complete(amount, len(mapped)):
            logger.warning(
                "⚠️ %s truncado com FETCH_LIMIT=%d (%d itens). "
                "Refazendo fetch completo (amount=0) para análise correta.",
                key,
                amount,
                len(mapped),
            )
            raw, amount = self._raw_fetch(key, user_id, amount=0)
            mapped = self._store_raw(key, raw, amount)
            if not _is_complete(amount, len(mapped)):
                # amount=0 is always complete by definition; defensive only
                raise RuntimeError(
                    f"Não foi possível obter lista completa de {key}."
                )

        return mapped

    def _raw_fetch(
        self, key: str, user_id: int, *, amount: int
    ) -> tuple[dict[Any, Any], int]:
        label = "full" if amount == 0 else str(amount)
        logger.info("📥 Buscando %s (amount=%s)...", key, label)
        if key == "followers":
            return self._client.user_followers(user_id, amount=amount), amount
        if key == "following":
            return self._client.user_following(user_id, amount=amount), amount
        raise ValueError(f"Chave de relação desconhecida: {key}")

    def _store_raw(
        self, key: str, raw: dict[Any, Any], fetch_amount: int
    ) -> RelationMap:
        mapped = to_relation_map(raw)
        complete = _is_complete(fetch_amount, len(mapped))
        if not complete:
            logger.warning(
                "⚠️ %s parcial: %d itens com amount=%d.",
                key,
                len(mapped),
                fetch_amount,
            )
        self.cache.set(
            key, mapped, complete=complete, fetch_amount=fetch_amount
        )
        logger.info(
            "✅ %s em cache: %d (%s)",
            key,
            len(mapped),
            "full" if complete else "partial",
        )
        return mapped

    @staticmethod
    def _export_rows(users: RelationMap) -> list[FollowerData]:
        return [
            {
                "id": str(pk),
                "username": u.username,
                "full_name": u.full_name,
                "is_private": u.is_private,
                "is_verified": u.is_verified,
                "follower_count": u.follower_count,
                "following_count": u.following_count,
                "media_count": u.media_count,
                "biography": u.biography,
                "external_url": u.external_url,
            }
            for pk, u in users.items()
        ]
