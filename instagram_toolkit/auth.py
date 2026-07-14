"""
Serviço de autenticação desacoplado da UI.
Emite logging em vez de print() para permitir reutilização fora da CLI.
"""

import json
import logging
from urllib.parse import unquote

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
                if self._try_credentials(client):
                    return True
                raise AuthenticationError(
                    "Falha na autenticação por usuário/senha."
                )

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
            session_id = unquote(self.config.session_id or "")
            client.login_by_sessionid(session_id)
            logger.info("✅ Autenticado com Session ID.")
            return True
        except (ClientLoginRequired, ChallengeRequired, OSError) as e:
            logger.warning("Falha no Session ID: %s", e)
            return False
        except Exception as e:
            logger.warning("Falha inesperada no Session ID: %s", e)
            return False

    def _load_cookies_dict(self) -> dict[str, str]:
        with self.config.cookies_file.open("r", encoding="utf-8") as f:
            cookies_data = json.load(f)
        match cookies_data:
            case list():
                return {
                    c["name"]: c["value"]
                    for c in cookies_data
                    if isinstance(c, dict) and "name" in c and "value" in c
                }
            case dict():
                return {str(k): str(v) for k, v in cookies_data.items()}
            case _:
                return {}

    def _try_cookies(self, client: Client) -> bool:
        logger.info("🍪 Carregando cookies de %s...", self.config.cookies_file)
        try:
            formatted = self._load_cookies_dict()
            if not formatted:
                logger.warning("Arquivo de cookies vazio ou formato inválido.")
                return False

            session_id = formatted.get("sessionid") or formatted.get("session_id")
            if not session_id:
                logger.warning(
                    "Cookie sessionid não encontrado em %s.", self.config.cookies_file
                )
                return False

            # Browser exports often percent-encode ':' as %3A
            session_id = unquote(session_id)
            # login_by_sessionid already validates via user_info
            client.login_by_sessionid(session_id)

            # Apply remaining cookies on the private session when available
            for name, value in formatted.items():
                if name in ("sessionid", "session_id"):
                    continue
                try:
                    client.private.cookies.set(
                        name, unquote(str(value)), domain=".instagram.com"
                    )
                except Exception:
                    pass

            logger.info("✅ Autenticado via cookies (user: %s).", client.username)
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
            raise AuthenticationError(f"Erro de I/O no login: {e}") from e
        except Exception as e:
            raise AuthenticationError(f"Erro no login: {e}") from e
