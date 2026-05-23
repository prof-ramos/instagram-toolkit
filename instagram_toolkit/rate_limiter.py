"""
RateLimiter dedicado com backoff exponencial e jitter.
Desacopla a lógica de espera do serviço principal.
"""

import logging
import random
import time

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
        """Delay simples entre operações normais."""
        lo = min_sec if min_sec is not None else self.base_delay_min
        hi = max_sec if max_sec is not None else self.base_delay_max
        time.sleep(random.uniform(lo, hi))

    def backoff(self, attempt: int) -> float:
        """
        Calcula e aplica backoff exponencial com jitter opcional.
        Retorna o tempo efetivamente aguardado.
        """
        wait = min(self.backoff_base * (self.backoff_multiplier ** (attempt - 1)), self.max_backoff)
        if self.jitter:
            wait = random.uniform(wait * 0.8, wait * 1.2)
        logger.warning("⏳ Rate limit detectado. Backoff: %.1fs (tentativa %d)", wait, attempt)
        time.sleep(wait)
        return wait

    def follow_delay(self) -> None:
        """Delay específico para operações de follow (mais conservador)."""
        self.delay(2.5, 4.5)

    def unfollow_delay(self) -> None:
        """Delay específico para operações de unfollow (mais conservador)."""
        self.delay(3.0, 5.0)
