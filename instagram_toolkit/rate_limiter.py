"""
RateLimiter dedicado com backoff exponencial e jitter.
Desacopla a lógica de espera do serviço principal.
"""

import logging
import random
import time

from .config import RateLimitError

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Gerencia delays entre operações para evitar rate limiting.
    Suporta delay simples, backoff exponencial e jitter configurável.
    """

    def __init__(
        self,
        base_delay_min: float = 1.8,
        base_delay_max: float = 3.8,
        backoff_base: float = 45.0,
        backoff_multiplier: float = 1.5,
        max_backoff: float = 300.0,
        jitter: bool = True,
    ) -> None:
        self.base_delay_min = base_delay_min
        self.base_delay_max = base_delay_max
        self.backoff_base = backoff_base
        self.backoff_multiplier = backoff_multiplier
        self.max_backoff = max_backoff
        self.jitter = jitter

    def delay(self, min_sec: float | None = None, max_sec: float | None = None) -> None:
        """Pausa a execução por um intervalo aleatório entre os limites fornecidos."""
        lo = min_sec if min_sec is not None else self.base_delay_min
        hi = max_sec if max_sec is not None else self.base_delay_max
        time.sleep(random.uniform(lo, hi))

    def backoff(self, attempt: int) -> float:
        """
        Aplica espera exponencial com jitter opcional.
        Levanta RateLimitError caso o tempo de espera atinja o máximo permitido.
        """
        wait = min(self.backoff_base * (self.backoff_multiplier ** (attempt - 1)), self.max_backoff)
        if wait >= self.max_backoff:
            raise RateLimitError("Rate limit backoff exceeded maximum configured wait")
        if self.jitter:
            wait = random.uniform(wait * 0.8, wait * 1.2)
        logger.warning("⏳ Rate limit detectado. Backoff: %.1fs (tentativa %d)", wait, attempt)
        time.sleep(wait)
        return wait

    def follow_delay(self) -> None:
        """Aguarda um intervalo aleatório maior antes de executar uma operação de follow."""
        self.delay(2.5, 4.5)

    def unfollow_delay(self) -> None:
        """Aguarda um intervalo aleatório maior antes de executar uma operação de unfollow."""
        self.delay(3.0, 5.0)
