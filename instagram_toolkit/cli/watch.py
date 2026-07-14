"""
Watch-mode loop for automated tracking.
"""

import time
from typing import Callable

__all__ = ["run_watch_loop"]


def run_watch_loop(tracker_fn: Callable[[], None], interval_minutes: int) -> None:
    if interval_minutes <= 0:
        raise ValueError("Intervalo deve ser positivo")
    print(
        f"🔄 Watch mode ativo — verificando a cada {interval_minutes} min. "
        "Ctrl+C para parar.\n"
    )
    try:
        while True:
            tracker_fn()
            print(f"\n⏳ Próxima verificação em {interval_minutes} min...\n")
            time.sleep(interval_minutes * 60)
    except KeyboardInterrupt:
        print("\n👋 Watch mode encerrado.")
