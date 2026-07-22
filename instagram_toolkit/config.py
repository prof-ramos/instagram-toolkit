"""
Configuração centralizada, constantes e exceções do toolkit.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

MAX_SNAPSHOTS: int = 10
DEFAULT_TTL: float = 300.0
DEFAULT_DELAY_MIN: float = 1.8
DEFAULT_DELAY_MAX: float = 3.8

# 0 = buscar lista completa (amount=0 no instagrapi).
# Override: INSTAGRAM_FETCH_LIMIT=500
DEFAULT_FETCH_LIMIT: int = 0

_NumberT = TypeVar("_NumberT", int, float)


def _resolve_env_number(
    name: str, default: _NumberT, cast: type[_NumberT], floor: _NumberT
) -> _NumberT:
    """Lê `name` do ambiente e aplica `cast`. Ausente, vazio, inválido ou
    não-finito (inf/nan, quando cast=float) vira `default`. O resultado nunca
    fica abaixo de `floor`."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = cast(raw)
    except ValueError:
        return default
    if isinstance(value, float) and not math.isfinite(value):
        return default
    return max(floor, value)


def resolve_fetch_limit() -> int:
    """Retorna o limite de fetch (0 = sem teto). Valores inválidos viram 0."""
    return _resolve_env_number("INSTAGRAM_FETCH_LIMIT", DEFAULT_FETCH_LIMIT, int, 0)


def resolve_cache_ttl() -> float:
    """Retorna o TTL do cache em segundos. Valores ausentes, inválidos ou
    não-finitos (inf/nan) viram DEFAULT_TTL; valores negativos viram 0.0."""
    return _resolve_env_number("INSTAGRAM_CACHE_TTL", DEFAULT_TTL, float, 0.0)


# Compat: imports legados `from .config import FETCH_LIMIT`
FETCH_LIMIT: int = resolve_fetch_limit()


@dataclass
class Config:
    username: str | None = field(default_factory=lambda: os.getenv("INSTAGRAM_USERNAME"))
    password: str | None = field(default_factory=lambda: os.getenv("INSTAGRAM_PASSWORD"))
    session_id: str | None = field(default_factory=lambda: os.getenv("INSTAGRAM_SESSION_ID"))
    settings_file: Path = field(default_factory=lambda: Path("instagrapi.json"))
    cookies_file: Path = field(default_factory=lambda: Path("cookies.json"))
    history_file: Path = field(default_factory=lambda: Path("followers_history.json"))
    backup_dir: Path = field(default_factory=lambda: Path("history_backups"))
    fetch_limit: int = field(default_factory=resolve_fetch_limit)
    cache_ttl: float = field(default_factory=resolve_cache_ttl)


class InstagramToolkitError(Exception):
    """Exceção base para o toolkit do Instagram."""


class AuthenticationError(InstagramToolkitError):
    """Exceção para falhas de autenticação."""


class RateLimitError(InstagramToolkitError):
    """Exceção para limites de requisição excedidos."""


class UserNotFoundError(InstagramToolkitError):
    """Exceção quando um usuário não é encontrado."""
