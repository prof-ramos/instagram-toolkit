"""
Serviço de rastreamento de seguidores ao longo do tempo.
"""

import logging
import time
from pathlib import Path

from instagrapi import Client
from instagrapi.exceptions import ClientError

from .models import TrackerResult
from .storage import HistoryStorage

logger = logging.getLogger(__name__)


class TrackerService:
    """
    Responsabilidade única: detectar ganhos e perdas de seguidores
    comparando snapshots do histórico.
    """

    def __init__(self, client: Client, storage: HistoryStorage) -> None:
        self.cl = client
        self.storage = storage

    def get_all_followers_safe(
        self, user_id: int, max_retries: int = 3
    ) -> dict:
        """Fetch completo sem limite (para tracker), com retry e backoff."""
        last_exc: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.info("📥 Carregando todos os seguidores (tentativa %d/%d)...", attempt, max_retries)
                followers = self.cl.user_followers(user_id, amount=0)
                logger.info("✅ %d seguidores carregados.", len(followers))
                return followers
            except ClientError as e:
                last_exc = e
                if "rate" in str(e).lower():
                    wait = 45 * attempt
                    logger.warning("⏳ Rate limit. Aguardando %ds...", wait)
                    time.sleep(wait)
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
        current = self.get_all_followers_safe(self.cl.user_id)
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
