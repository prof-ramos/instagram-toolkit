"""
Configuração centralizada, constantes e exceções do toolkit.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

MAX_SNAPSHOTS: int = 10
FETCH_LIMIT: int = 500
DEFAULT_TTL: float = 300.0
DEFAULT_DELAY_MIN: float = 1.8
DEFAULT_DELAY_MAX: float = 3.8


@dataclass
class Config:
    username: str | None = field(default_factory=lambda: os.getenv("INSTAGRAM_USERNAME"))
    password: str | None = field(default_factory=lambda: os.getenv("INSTAGRAM_PASSWORD"))
    session_id: str | None = field(default_factory=lambda: os.getenv("INSTAGRAM_SESSION_ID"))
    settings_file: Path = field(default_factory=lambda: Path("instagrapi.json"))
    cookies_file: Path = field(default_factory=lambda: Path("cookies.json"))
    history_file: Path = field(default_factory=lambda: Path("followers_history.json"))
    backup_dir: Path = field(default_factory=lambda: Path("history_backups"))


class InstagramToolkitError(Exception):
    """Exceção base para o toolkit do Instagram."""


class AuthenticationError(InstagramToolkitError):
    """Exceção para falhas de autenticação."""


class RateLimitError(InstagramToolkitError):
    """Exceção para limites de requisição excedidos."""


class UserNotFoundError(InstagramToolkitError):
    """Exceção quando um usuário não é encontrado."""
