"""
Serviço de autenticação desacoplado da UI.
Emite logging em vez de print() para permitir reutilização fora da CLI.
"""

import json
import logging

from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, ClientLoginRequired

from .config import Config
from .config import AuthenticationError
from .storage import HistoryStorage

logger = logging.getLogger(__name__)


class AuthService:
    """
    Autentica o cliente instagrapi.
    Usa logging em vez de print(), desacoplando completamente da UI.
    """

    def __init__(self, config: Config, storage: HistoryStorage) -> None:
        self.config = config
        self.storage = storage

    def authenticate(self, client: Client) -> bool:
        """
        Tenta autenticar via Session ID, cookies, sessão salva
        ou credenciais (nessa ordem de preferência).
        """
        try:
            if self.config.session_id:
                if self._try_session_id(client):
                    return True

            if self.config.cookies_file.exists():
                if self._try_cookies(client):
                    return True

            if self.config.settings_file.exists():
                if self._try_saved_session(client):
                    return True

            if self.config.username and self.config.password:
                return self._try_credentials(client)

            raise AuthenticationError(
                "Nenhuma forma de autenticação disponível. "
                "Configure INSTAGRAM_SESSION_ID, cookies.json ou usuário/senha no .env."
            )
        except AuthenticationError:
            raise
        except Exception as e:
            logger.warning("Falha na autenticação: %s", e)
            raise AuthenticationError(f"Falha na autenticação: {e}") from e

    def _try_session_id(self, client: Client) -> bool:
        logger.info("🔑 Tentando autenticação via Session ID...")
        try:
            client.login_by_sessionid(self.config.session_id)
            logger.info("✅ Autenticado com Session ID.")
            return True
        except (ClientLoginRequired, ChallengeRequired, OSError) as e:
            logger.warning("Falha no Session ID: %s", e)
            return False
        except Exception as e:
            logger.warning("Falha inesperada no Session ID: %s", e)
            return False

    def _try_cookies(self, client: Client) -> bool:
        logger.info("🍪 Carregando cookies de %s...", self.config.cookies_file)
        try:
            with self.config.cookies_file.open("r", encoding="utf-8") as f:
                cookies_data = json.load(f)
            match cookies_data:
                case list():
                    formatted = {
                        c["name"]: c["value"]
                        for c in cookies_data
                        if isinstance(c, dict) and "name" in c and "value" in c
                    }
                case dict():
                    formatted = cookies_data
                case _:
                    formatted = {}
            client.set_cookies(formatted)
            client.get_timeline_feed()
            logger.info("✅ Autenticado via cookies.")
            return True
        except (ClientLoginRequired, ChallengeRequired, OSError, json.JSONDecodeError) as e:
            logger.warning("Falha nos cookies: %s", e)
            return False
        except Exception as e:
            logger.warning("Falha inesperada nos cookies: %s", e)
            return False

    def _try_saved_session(self, client: Client) -> bool:
        logger.info("📁 Carregando sessão salva de %s...", self.config.settings_file)
        try:
            client.load_settings(str(self.config.settings_file))
            client.get_timeline_feed()
            logger.info("✅ Sessão carregada do cache.")
            return True
        except (ClientLoginRequired, ChallengeRequired, OSError) as e:
            logger.warning("Sessão expirada ou inválida: %s", e)
            return False
        except Exception as e:
            logger.warning("Falha inesperada ao carregar sessão: %s", e)
            return False

    def _try_credentials(self, client: Client) -> bool:
        logger.info("🔐 Fazendo login com usuário e senha...")
        try:
            client.login(self.config.username, self.config.password)
            self.storage.secure_write_json(
                self.config.settings_file, client.get_settings()
            )
            logger.info("✅ Login realizado e sessão salva.")
            return True
        except ChallengeRequired:
            raise AuthenticationError(
                "Desafio de segurança detectado. Resolva no app do Instagram."
            )
        except ClientLoginRequired:
            raise AuthenticationError("Credenciais inválidas.")
        except OSError as e:
            logger.warning("Erro de I/O no login: %s", e)
            return False
        except Exception as e:
            raise AuthenticationError(f"Erro no login: {e}") from e
